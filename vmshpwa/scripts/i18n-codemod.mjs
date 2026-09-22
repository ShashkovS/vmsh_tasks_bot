#!/usr/bin/env node
// Wraps Russian UI copy of the given files in Lingui macros (docs/i18n.md):
// - JSX text runs (text, simple values, inline elements) → <Trans>…</Trans>;
// - Russian string/template literals in code and JSX attributes → t`…`
//   from @lingui/core/macro (the interface reloads on a language switch, so
//   the global i18n is always the active language when code runs);
// - module-level object properties → lazy getters `get key() { return t`…` }`.
// Data contexts (comparisons, keys, z.literal/enum, regex, storage, form values)
// are skipped. Everything that needs a decision is reported, not rewritten.
// Usage: node scripts/i18n-codemod.mjs [--dry] file...
import { readFileSync, writeFileSync } from 'node:fs'
import { relative } from 'node:path'

import ts from 'typescript'

const CYRILLIC = /[А-Яа-яЁё]/
const SKIPPED_ATTRIBUTES = new Set([
  'value',
  'defaultValue',
  'name',
  'id',
  'key',
  'className',
  'href',
  'to',
  'type',
  'role',
  'lang',
  'pattern',
  'accept',
  'autoComplete',
  'inputMode',
  'htmlFor',
  'form',
  'method',
  'action',
  'target',
  'rel',
  'src',
  'download',
  'mask',
])
const SKIPPED_CALLEES = new Set([
  'localeCompare',
  'toLocaleLowerCase',
  'toLocaleUpperCase',
  'literal',
  'enum',
  'includes',
  'startsWith',
  'endsWith',
  'indexOf',
  'lastIndexOf',
  'split',
  'replace',
  'replaceAll',
  'match',
  'matchAll',
  'search',
  'test',
  'exec',
  'RegExp',
  'querySelector',
  'querySelectorAll',
  'getItem',
  'setItem',
  'removeItem',
  'getAttribute',
  'setAttribute',
  'getByText',
  'getByRole',
  'getByLabel',
  'has',
  'delete',
  'normalize',
])
const INLINE_TAGS = new Set([
  'a',
  'abbr',
  'b',
  'bdi',
  'br',
  'code',
  'em',
  'i',
  'kbd',
  'mark',
  's',
  'small',
  'span',
  'strong',
  'sub',
  'sup',
  'time',
  'u',
])
const MACRO_COMPONENTS = new Set(['Trans', 'Plural', 'Select', 'SelectOrdinal'])

const args = process.argv.slice(2)
const dry = args.includes('--dry')
const files = args.filter((arg) => arg !== '--dry')

function isFunctionLike(node) {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isFunctionExpression(node) ||
    ts.isArrowFunction(node) ||
    ts.isMethodDeclaration(node) ||
    ts.isGetAccessorDeclaration(node) ||
    ts.isSetAccessorDeclaration(node) ||
    ts.isConstructorDeclaration(node)
  )
}

function insideFunction(node) {
  for (let current = node.parent; current; current = current.parent) {
    if (isFunctionLike(current)) return true
  }
  return false
}

function calleeName(expression) {
  if (ts.isIdentifier(expression)) return expression.text
  if (ts.isPropertyAccessExpression(expression)) return expression.name.text
  return undefined
}

function tagName(element) {
  const opening = ts.isJsxElement(element) ? element.openingElement : element
  const name = opening.tagName
  return ts.isIdentifier(name) ? name.text : name.getText()
}

function escapeTemplate(text) {
  let result = ''
  for (const character of text) {
    if (character === '\\') result += '\\\\'
    else if (character === '`') result += '\\`'
    else if (character === '\n') result += '\\n'
    else if (character === '\r') result += '\\r'
    else if (character === '\t') result += '\\t'
    else result += character
  }
  return result.replaceAll('${', '\\${')
}

/** Why a Cyrillic literal must not be translated, or undefined to translate it. */
function dataContext(node) {
  const parent = node.parent
  if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) return 'module specifier'
  if (ts.isLiteralTypeNode(parent)) return 'type'
  if (
    (ts.isPropertyAssignment(parent) ||
      ts.isPropertySignature(parent) ||
      ts.isMethodDeclaration(parent) ||
      ts.isEnumMember(parent) ||
      ts.isGetAccessorDeclaration(parent)) &&
    parent.name === node
  ) {
    return 'property name'
  }
  if (ts.isElementAccessExpression(parent) && parent.argumentExpression === node) return 'key'
  if (ts.isCaseClause(parent)) return 'case label'
  if (
    ts.isBinaryExpression(parent) &&
    [
      ts.SyntaxKind.EqualsEqualsEqualsToken,
      ts.SyntaxKind.ExclamationEqualsEqualsToken,
      ts.SyntaxKind.EqualsEqualsToken,
      ts.SyntaxKind.ExclamationEqualsToken,
      ts.SyntaxKind.InKeyword,
    ].includes(parent.operatorToken.kind)
  ) {
    return 'comparison'
  }
  if (ts.isJsxAttribute(parent)) {
    const name = parent.name.getText()
    if (SKIPPED_ATTRIBUTES.has(name) || name.startsWith('data-')) return `attribute ${name}`
  }
  if (ts.isJsxExpression(parent) && ts.isJsxAttribute(parent.parent)) {
    const name = parent.parent.name.getText()
    if (SKIPPED_ATTRIBUTES.has(name) || name.startsWith('data-')) return `attribute ${name}`
  }
  // Walk out of arrays/conditionals to the call that receives the literal.
  let holder = parent
  while (
    holder &&
    (ts.isArrayLiteralExpression(holder) ||
      ts.isConditionalExpression(holder) ||
      ts.isParenthesizedExpression(holder) ||
      ts.isAsExpression(holder) ||
      ts.isSatisfiesExpression(holder))
  ) {
    holder = holder.parent
  }
  if (holder && (ts.isCallExpression(holder) || ts.isNewExpression(holder))) {
    const name = calleeName(holder.expression)
    if (name && SKIPPED_CALLEES.has(name)) return `argument of ${name}()`
    if (ts.isPropertyAccessExpression(holder.expression)) {
      const target = holder.expression.expression
      if (ts.isIdentifier(target) && target.text === 'console') return 'console'
    }
  }
  return undefined
}

function lineOf(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
}

function transformFile(path) {
  const text = readFileSync(path, 'utf8')
  const kind = path.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const sourceFile = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, kind)
  const edits = []
  const report = []
  const wrappedRanges = []
  let usesT = false
  let usesTrans = false
  const declaresT = /(?:\(|,\s*|\b(?:const|let|var|function)\s+)t\s*(?:[,)=:]|=>)/.test(text)
  const tName = declaresT ? 'translate' : 't'

  const inWrappedRun = (node) => {
    const position = node.getStart(sourceFile)
    return wrappedRanges.some(([start, end]) => position >= start && position < end)
  }

  function childKind(child) {
    if (ts.isJsxText(child)) return child.containsOnlyTriviaWhiteSpaces ? 'space' : 'text'
    if (ts.isJsxExpression(child)) {
      const expression = child.expression
      if (!expression) return 'break'
      if (ts.isStringLiteral(expression) || ts.isNoSubstitutionTemplateLiteral(expression)) {
        return 'value'
      }
      if (
        ts.isIdentifier(expression) ||
        ts.isPropertyAccessExpression(expression) ||
        ts.isNumericLiteral(expression)
      ) {
        return 'value'
      }
      return 'break'
    }
    if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) {
      const name = tagName(child)
      if (MACRO_COMPONENTS.has(name)) return 'break'
      if (!INLINE_TAGS.has(name)) return 'break'
      if (ts.isJsxElement(child)) {
        const inner = child.children.map(childKind)
        if (inner.some((kindOfChild) => kindOfChild === 'break')) return 'break'
      }
      return 'inline'
    }
    return 'break'
  }

  function visitJsxChildren(children) {
    let run = []
    const flush = () => {
      while (run.length && childKind(run[0]) === 'space') run.shift()
      while (run.length && childKind(run.at(-1)) === 'space') run.pop()
      // A lone inline element (e.g. <span className="sr-only">…</span>) is not
      // a sentence of its own: translate inside it instead of wrapping it.
      if (run.length === 1 && childKind(run[0]) === 'inline') run = []
      const hasRussianText = run.some(
        (child) =>
          (ts.isJsxText(child) && CYRILLIC.test(child.text)) ||
          ((ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) &&
            CYRILLIC.test(child.getText(sourceFile))),
      )
      if (hasRussianText) {
        // JsxText spans its whole raw text from `pos`; keep surrounding
        // indentation outside the <Trans> element.
        const first = run[0]
        const last = run.at(-1)
        const start = ts.isJsxText(first)
          ? first.pos + (first.text.length - first.text.trimStart().length)
          : first.getStart(sourceFile)
        const end = ts.isJsxText(last)
          ? last.end - (last.text.length - last.text.trimEnd().length)
          : last.end
        edits.push({ start, end: start, text: '<Trans>' })
        edits.push({ start: end, end, text: '</Trans>' })
        wrappedRanges.push([start, end])
        usesTrans = true
      }
      run = []
    }
    for (const child of children) {
      if (childKind(child) === 'break') flush()
      else run.push(child)
    }
    flush()
  }

  function ownText(node) {
    if (ts.isTemplateExpression(node)) {
      return [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join('')
    }
    return node.text
  }

  function translateLiteral(node) {
    // Only the literal's own text counts: a template whose Russian lives in a
    // nested literal is a placeholder-only message and stays untouched.
    if (!CYRILLIC.test(ownText(node))) return
    // Literals that are JSX children of a <Trans> run become part of its message;
    // attribute values of inline elements inside the run are still translated.
    const isAttributeValue =
      ts.isJsxAttribute(node.parent) ||
      (ts.isJsxExpression(node.parent) && ts.isJsxAttribute(node.parent.parent))
    if (inWrappedRun(node) && !isAttributeValue) return
    const reason = dataContext(node)
    if (reason) {
      report.push(`${lineOf(sourceFile, node)}: skipped (${reason}) ${node.getText(sourceFile)}`)
      return
    }
    const start = node.getStart(sourceFile)
    const template = ts.isTemplateExpression(node)
      ? node.getText(sourceFile)
      : `\`${escapeTemplate(node.text)}\``
    const macro = `${tName}${template}`
    // Templates keep their source and only gain the tag, so edits inside their
    // placeholders never overlap this one.
    const tagTemplate = () => edits.push({ start, end: start, text: tName })
    if (!insideFunction(node)) {
      const parent = node.parent
      if (
        ts.isPropertyAssignment(parent) &&
        parent.initializer === node &&
        ts.isObjectLiteralExpression(parent.parent)
      ) {
        const name = parent.name.getText(sourceFile)
        edits.push({
          start: parent.getStart(sourceFile),
          end: parent.end,
          text: `get ${name}() {\n return ${macro}\n}`,
        })
        usesT = true
        return
      }
      report.push(`${lineOf(sourceFile, node)}: MANUAL module-level ${node.getText(sourceFile)}`)
      return
    }
    if (ts.isJsxAttribute(node.parent)) {
      edits.push({ start, end: node.end, text: `{${macro}}` })
    } else if (ts.isTemplateExpression(node)) {
      tagTemplate()
    } else {
      edits.push({ start, end: node.end, text: macro })
    }
    usesT = true
  }

  // JSX runs first so literals inside wrapped runs are left to <Trans>.
  const collectRuns = (node) => {
    if ((ts.isJsxElement(node) || ts.isJsxFragment(node)) && !inWrappedRun(node)) {
      const name = ts.isJsxElement(node) ? tagName(node) : ''
      if (!MACRO_COMPONENTS.has(name)) visitJsxChildren(node.children)
    }
    ts.forEachChild(node, collectRuns)
  }
  collectRuns(sourceFile)
  const visitLiterals = (node) => {
    if (ts.isTaggedTemplateExpression(node)) return
    // Text inside existing <Trans>/<Plural> already belongs to a message.
    if (ts.isJsxElement(node) && MACRO_COMPONENTS.has(tagName(node))) return
    if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateExpression(node)
    ) {
      translateLiteral(node)
      if (ts.isTemplateExpression(node)) {
        for (const span of node.templateSpans) visitLiterals(span.expression)
      }
      return
    }
    if (ts.isJsxText(node) && CYRILLIC.test(node.text) && !inWrappedRun(node)) {
      report.push(`${lineOf(sourceFile, node)}: MANUAL jsx text ${node.text.trim().slice(0, 60)}`)
    }
    ts.forEachChild(node, visitLiterals)
  }
  visitLiterals(sourceFile)

  // Russian-locale formatters → cached formatters of the active language.
  const i18nNames = new Set()
  const RUSSIAN_LOCALE = new Set(['ru', 'ru-RU'])
  const localeMethods = {
    toLocaleString: 'formatDateTime',
    toLocaleDateString: 'formatDate',
    toLocaleTimeString: 'formatTime',
  }
  const isRussianLocaleArgument = (argument) =>
    argument && ts.isStringLiteral(argument) && RUSSIAN_LOCALE.has(argument.text)
  const visitFormatters = (node) => {
    if (
      ts.isNewExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.expression.getText(sourceFile) === 'Intl' &&
      ['DateTimeFormat', 'NumberFormat'].includes(node.expression.name.text) &&
      isRussianLocaleArgument(node.arguments?.[0])
    ) {
      if (!insideFunction(node)) {
        report.push(`${lineOf(sourceFile, node)}: MANUAL module-level formatter`)
      } else {
        const helper = node.expression.name.text === 'DateTimeFormat' ? 'dateTimeFormat' : 'numberFormat'
        const locale = node.arguments[0]
        edits.push({
          start: node.getStart(sourceFile),
          end: locale.end,
          text: `${helper}(currentLocale()`,
        })
        i18nNames.add(helper)
        i18nNames.add('currentLocale')
      }
    }
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text in localeMethods &&
      isRussianLocaleArgument(node.arguments[0])
    ) {
      const receiver = node.expression.expression
      const receiverText = receiver.getText(sourceFile)
      const isDate =
        (ts.isNewExpression(receiver) && receiver.expression.getText(sourceFile) === 'Date') ||
        /^(d|date)$/.test(receiverText) ||
        node.expression.name.text !== 'toLocaleString'
      const helper = isDate ? localeMethods[node.expression.name.text] : 'formatNumber'
      const rest = node.arguments
        .slice(1)
        .map((argument) => argument.getText(sourceFile))
        .join(', ')
      edits.push({
        start: node.getStart(sourceFile),
        end: node.end,
        text: `${helper}(${receiverText}${rest ? `, ${rest}` : ''})`,
      })
      i18nNames.add(helper)
      return
    }
    ts.forEachChild(node, visitFormatters)
  }
  visitFormatters(sourceFile)

  if (edits.length === 0) return { changed: false, report }

  const imports = []
  if (usesT && !/from '@lingui\/core\/macro'/.test(text)) {
    imports.push(
      `import { ${tName === 't' ? 't' : 't as translate'} } from '@lingui/core/macro'`,
    )
  }
  if (usesTrans && !/from '@lingui\/react\/macro'/.test(text)) {
    imports.push(`import { Trans } from '@lingui/react/macro'`)
  }
  if (i18nNames.size > 0) {
    imports.push(`import { ${[...i18nNames].sort().join(', ')} } from '@vmsh/i18n'`)
  }
  let output = text
  for (const edit of edits.sort((a, b) => b.start - a.start || b.end - a.end)) {
    output = output.slice(0, edit.start) + edit.text + output.slice(edit.end)
  }
  if (imports.length > 0) {
    // Keep directive prologues such as 'use client' first.
    const prologue = /^(?:\s*(?:'[^']*'|"[^"]*");?[^\S\n]*\n)*/.exec(output)?.[0] ?? ''
    output = `${prologue}${imports.join('\n')}\n${output.slice(prologue.length)}`
  }
  if (!dry) writeFileSync(path, output)
  return { changed: true, report, tName }
}

let changedFiles = 0
for (const file of files) {
  const { changed, report, tName } = transformFile(file)
  if (changed) changedFiles += 1
  const name = relative(process.cwd(), file)
  if (changed || report.length) {
    console.log(`${changed ? 'M' : '·'} ${name}${tName === 'translate' ? ' (t as translate)' : ''}`)
    for (const line of report) console.log(`    ${line}`)
  }
}
console.log(`${changedFiles} file(s) ${dry ? 'would change' : 'changed'}`)
