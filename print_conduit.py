import sqlite3
import re
import pyperclip

NLIST = 7
NLEVEL = ''
FOR_MAILS = 1  # 1/0

conn = sqlite3.connect(r'db\88b1047644e68c3cceb7ff21e1190a90.db')
cur = conn.cursor()

cur.execute('''
    select distinct
    u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user,
    p.lesson || p.level || '.' || p.prob  || p.item as prob,
    max(r.verdict)
    from users u 
    join results r on r.student_id = u.id 
    join problems p on r.problem_id = p.id
    where (u.type = 1 and token not like 'pass%') and p.lesson = :NLIST and 
    (p.level = :NLEVEL or ''=:NLEVEL) 
    group by 1, 2
''', globals())
results = {(r[0], r[1]): str(max(r[2], 0)) for r in cur.fetchall()}
print(len(results))

cur.execute('''
    select u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user
    from users u 
    where u.type = 1 and token not like 'pass%'
    order by u.surname, u.name, u.token
''')
pupils = [x[0] for x in cur.fetchall()]


token_to_pupil = {}
for pupil in pupils:
    token, *__ = pupil.split('\t')
    token_to_pupil[token] = pupil
order = '''\
mu7fe4 ku7te7 da4he7 gu6ja7 ny2ma2 zy4he3 zu2re8 qa5sa6 xy3vu3 py4ra2 be7ce2 pe5su6 za9ra2 vu4ve5 jy4qe2 Ra4rU7 jy8fa8 du8gu2 ny5ba3 pa3by3 qy8du8 ta4he3 ve8qu8 we9wy4 na8be3 jy5mu3 fu7ry8 Cu5kU7 du4hu7 hu5te5 qy8we6 wu5qe3 du2ky6 ga4ce9 su3ja5 zy8mu5 zy6xy5 cu5py6 fe9ce2 ce9me6 qy9cy4 ra9va2 re7xe2 jy3fy8 pu3ky9 ga5ha5 ne6vy7 ve9pu6 tu9te6 xa4da8 wu2wu8 pa7gu6 ga8ze7 ne6ju7 pu3ky5 qa3su4 su6jy6 ze9FY5 gu9za5 qu6ka8 je9qu3 ze5xa2 ge3da6 ze4we9 my2su2 ta9ky9 ta9ny5 va4pu9 he7xa8 fy3re9 hu7ba7 hy6ce6 ra2cu4 va3mu8 wa7he5 xa9su5 zy8be8 ra6de9 ge4fe7 ru3gu8 za4cy4 qu6xa4 su4je4 sy5tu9 by7fe3 pa9vu5 qe4ru4 te3ja7 re7ga2 qy9re6 re4hu8 hu3je9 ja5re8 me3ju6 mu6be7 ru9fa8 te8ka3 vu2cy2 wu3ny4 nu4vu6 pa3de3 gA4Ry2 se8xe8 ky5du9 ty7ga4 xy5jy4 ra4du5 zu2fe2 xe7hu5 ty9DE6 de4gu6 fe9cy8 fu6fa4 ge3wa3 ha9ga2 na5hy7 Qy6dA3 ru4gu4 tu3cu4 ja9na5 xy5te8 pu8qy9 ce7xe3 my9ha4 NE2du2 qa4se3 qe9ga3 xa5de6 xy4zu5 xy9su4 zy4ha4 xu8by7 du3ja4 hy5pu9 ry5qu7 se9ke6 tu2ne5 vu8fu6 wy9sy4 ha2ke8 he8qe2 ca5pu9 fa2wa6 gu7te8 gy2mu4 na8ke4 pu5ny3 qu2ke8 su6ga2 by7re9 va2ca9 ve9we4 ba2ju3 ba4jy4 be2pa2 bu4re9 bu9da7 bu9ge9 by3zu8 by5qe4 by5ty3 by7be6 ca3bu3 ca6ne3 cy9mu2 da3cy7 du5pe4 du5vu3 du7tu7 dy9my4 fa6te2 fa8mu7 fe3be9 fe5zu9 fy3ze8 ga2cy2 ga2mu6 ga9ca4 ga9xa7 ge8gy6 gy6ja6 gy7my4 ha9mu9 ha9ny9 hu8ky2 hy4de9 ja9sy9 je7je3 je7jy4 je7wa4 jy2xy2 ka5hy6 ka6ma4 ku5sa3 ky9me7 ky9pu9 ma7he9 ma7se5 me8we4 my8qu9 na4we9 ne4by7 ne6ne5 ne9je9 ny9wa2 pa9ny6 pe7sa4 pu6zu3 py2qe8 py8qe6 qa6re2 qe7su7 qy7wu2 qy9gy6 re3se9 ru5sy9 ry5zu9 sa2we9 su4ty6 sy2se7 sy3ve4 ta3te8 ta9sy9 te5cu5 te9be9 va3tu7 vu8by2 vy3xe8 wY6mY8 wy9xy2 xa3ju9 xe5ty4 xe9ha3 xy2vy8 xy7zy8 mu3se8 xy5ne6 sa5ge9 fa9be6 sa8de3 cu9ta6 na3je3 ja4ku2 ge4wa9 ge4sy7 xy5ja9 pu6ju2 ha3zy8 hy4qy8 hy4pu3 wy3my8 wu4xu2 ga6ce6 nu9cu9 my7za8 xu6ja6 he4py5 pa9ce6 te7gu5 xu5se2 nu4te3 qe9qe3 nu2pu8 ve6fy3 ve9ju6 qu8da5 ce6du5 ky6hy6 gy8ra8 du5mu4 su5xu3 fy2pu8 we3fu7 nu8gu3 zy4su3 qy7ru8 su9sa3 ca5he9 sy9du2 Qa4Da2 ja4we4 fa3na2 fe2zu2 fe5ke9 ne7xy9 by9ru9 sy5xy5 fu5mu8 da4ca4 ke4na7 xy9qa4 xa5my2 cy3qe7 gu6ju5 sa9pu8 ze8ry8 dy3ke6 va3ve2 ta9ra6 dy3zy3 re5ha2 za5ca8 ry5vu4 ce9ba9 ty7ne6 he4ba3 ny2jy9 ma6jy3 hy5gy6 be3vy9 ne5jy7 qe9ra2 ce9ju4 wa2vu5 vy4ga5 na7xa7 vy7tu2 qy5ra2 ve7ry6 hy3ny5 xa6vu7 ke6wa3 ty9je5 pe6ry6 je8pa7 sy2zy4 nu9we6 ku4qe5 zy5ka2 nu5je7 cu5NE8 qa8qu5 me5re7 xe3qe9 ha7pa6 my6fa6 hu7ka2 ca8gy3 xe9fu9 qu9me3 he6su5 qa3ce9 sy8sy5 me3re4 vu8zu6 cu3zy2 qe3je5 ja9dy8 ne5xa7 ka2qy6 ga7ve5 qe4su7 my3ju5 fu7fy9 fu3cu3 fu3ku4 za8he8 hy8du6 vU3xY2 bu8vu2 wu2fu8 zu9cu5 qa2xy2 hy9za5 fe2sy8 ba5wa5 za3vu7 fa2fa8 fe8jy5 cy2fa9 wu3wu5 va5su2 jy4ra2 gu5we5 ha7ja2 be3fy6 tu7ra7 dy2xa6 je4qe3 ge2jy7 qa2ty5 vy3wu3 ty9ja7 da5ge6 gu3ry7 mu8by3 he6ce4 sa4ba4 ne3my7 jy3fa7 ze9ka3 qu8da9 ty8jy7 fy6ky6 hu3ru7 pe8qa4 ky4ka7 ru4qe9 ve2ze3 qu8ze7 cy5ca7 zy4py4 ne4qa8 tu9wu9 ta9dy6 ky2hu6 ra3we3 nu6by2 dy3hy9 ma2ka7 ku7pa6 ze9pe9 zu5fe8 ry4na5 ca7ga4 qu3za8 ja2xu9 he5ha9 ge4va5 my4me4 su5ma6 vu4gu9 qY2Ry8 gu5xu8 xu9wu9 va7xu6 sa7pu5 dy7we7 da5fa7 qe4qu4 vu7qu9 pe2sy8 za4fy8 vu8ty2 ne7su6 xe9he5 ny5py2 ve8dy2 he4su3 ra9by9 ma7gu6 xa7ta7 te8xa5 ra9hu5 mu7ke4 wa6ce6 pu8na7 bu3pe2 xy7ju7 su8ge4 qy5cu5 ga5ne8 he7xe9 hy9ky3 be4be3 fy3ka8 py8ce5 se6vu9 ty7ne2 cE9Re8 xe2ky3 ke6hu7 ny3py2 py7xe3 ru3pa6 ta2we7 vu2hu7 fu7py6 qu7xu5 ka4he6 wa6pe9 xy3ky4 zy3ne4 ce6ky3 ge3ge2 xa7nu7 xa3zu4 dy8ne3 pe2my3 ty6ta6 ca6xa5 ja3fe7 zu5xe4 ze9cy4 ja5pu7 da3tu4 je6fe7 xa7ca3 hy7mu6 by3xa9 sa4dy7 jy8py9 ta7fa3 pu6ga6 za8xe7 hy7qy9 vy4fu8 du5xy9 ka7dy2 ku3we4 ju8ja6 dy9ty8 da6ca4 ce5wy9 cy8na8 be6ma4 xu6ra9 ju5we3 ry7ca6 qa3gy6 wa8py6 dy2zy5 cy8ce5 ju2cu9 ky2ka6 wa6fu2 sy9mu4 gu9su2 re9ke9 mE2rA2 by3wy7 ha9ta5 ce5py2 me6zy8 Ju4Qe6 re7gy3 sa9qu8 ra9ru3 fy2we9 fa4fy7 ny5ry8 cy9ju9 jy3wy4 ty6ta9 za4gu3 be6ka2 pe8he5 ja3he5 bu4fu5 tu4jy4 pa2bu8 fy2ha9 ja5du5 fa7su6 xu8me6 my8va3 tu9hy5 mu5su4 gu4da5 ve2hu9 qu6mu9 ra7je7 pe7ha6 ta8we8 nu5ky2 qa6gy2 pu6wu7 by6te4 wu9ce2 tu4ce7 qy2ge3 nE7Qu5 jy9he6 ma8hu8 va5me9 ry7na5 he4ku5 ze4hy2 se8fe8 se8we4 my7ta2 qe3su7 we2sy5 ra6ma8 ce8dy4 pe7ga7 qe2ja8 xa7ve8 fa5fu6 xu8qe9 ga3ga8 qu2qe9 su7re6 fy5ky8 ju5gu7 ku4ca2 ka9pe5 py3qy2 fy3bu8 ba8za5 va4gu8 ga3vy5 vy4ku3 nu5zy9
'''

ordered_pupils = [token_to_pupil[token] for token in order.split()]
pupils = ordered_pupils






cur.execute('''
    select p.lesson || p.level || '.' || p.prob  || p.item as prob
    from problems p
    where p.lesson = :NLIST and (p.level = :NLEVEL or ''=:NLEVEL)
''', globals())
problems = set({x[0] for x in cur.fetchall()})

formated_problems = []
for problem in problems:
    m = re.fullmatch('(\d+)([а-я])\.(\d+)([а-я]?)', problem)
    lst, lvl, prb, itm = m.groups()
    formated_problems.append((f'{int(lst):02}{lvl}.{int(prb):02}{itm}', problem))
formated_problems.sort()
table = [[''] * (len(problems) + 2) for __ in range(len(pupils) + 1)]
table[0][0] = 'token\tФамилия\tИмя\tнач/прод'
table[0][1] = f'{NLIST:02}{NLEVEL}.Н'
for c, (formatted, problem) in enumerate(formated_problems, start=2):
    if FOR_MAILS:
        formatted = formatted.strip('cс').lstrip('0')
        formatted = formatted if '.' not in formatted else formatted[formatted.find('.')+1:].strip('cс').lstrip('0')
        formatted = 'c' + formatted
    table[0][c] = formatted
for r, pupil in enumerate(pupils, start=1):
    table[r][0] = pupil


for r, pupil in enumerate(pupils, start=1):
    for c, (formatted, problem) in enumerate(formated_problems, start=2):
        table[r][c] = results.get((pupil, problem), '')
    table[r][1] = '1' if any(table[r][2:]) else ''

startFrom = 0 if FOR_MAILS else 1
stable = '\n'.join('\t'.join(row[startFrom:]) for row in table if not FOR_MAILS or any(row[1:]))
pyperclip.copy(stable)
print(stable)
