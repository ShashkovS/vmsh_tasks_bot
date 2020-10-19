import sqlite3
import re
import pyperclip

NLIST = 6
NLEVEL = 'п'
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
nu4te3 qe9qe3 hu7ka2 cy3qe7 gu6ju5 nu2pu8 wa2vu5 sa9pu8 vy4ga5 ry7ca6 fa2fa8 ve6fy3 ze8ry8 ve9ju6 du5mu4 na7xa7 dy3ke6 su5xu3 su8ge4 ja2xu9 va3ve2 fy2pu8 vy7tu2 qy5ra2 we3fu7 mu7fe4 nu8gu3 qu8da5 fu3cu3 ca8gy3 zy4su3 qy7ru8 ve7ry6 su9sa3 ca5he9 he5ha9 fu3ku4 ta9ra6 fe8jy5 ga3ga8 ge4va5 dy3zy3 hy3ny5 ja5pu7 ku7te7 xa6vu7 ke6wa3 my4me4 qy5cu5 cy2fa9 fy6ky6 pa9ce6 wu3wu5 ce6du5 re5ha2 sy9du2 hu3ru7 ga5ne8 pe8qa4 ty9je5 Qa4Da2 my7za8 te7gu5 da4he7 za5ca8 va5su2 xu5se2 ja4we4 xu6ja6 ky6hy6 gu6ja7 qa3gy6 ny2ma2 za8he8 zy4he3 pe6ry6 su5ma6 vu4gu9 xe9fu9 je8pa7 hy8du6 zu2re8 ky4ka7 fa3na2 qa5sa6 xy3vu3 qu9me3 py4ra2 nu9cu9 qY2Ry8 gu5xu8 he7xe9 vU3xY2 sy2zy4 xu9wu9 ry5vu4 fe2zu2 va7xu6 nu9we6 ru4qe9 fe5ke9 ce9ba9 hy9ky3 gy8ra8 jy4ra2 sa7pu5 ty7ne6 he6su5 be4be3 fa4fy7 gu5we5 ne7xy9 he4ba3 fy3ka8 be7ce2 dy7we7 pe5su6 za9ra2 ha7ja2 da5fa7 qu2qe9 tu9hy5 ku4qe5 nu5ky2 by9ru9 qa3ce9 py8ce5 ny2jy9 qe4qu4 qe2ja8 vu4ve5 ve2ze3 qu8ze7 mu5su4 vu7qu9 cy5ca7 pe2sy8 za4fy8 sy8sy5 zy4py4 sy5xy5 me3re4 be3fy6 bu8vu2 vu8zu6 jy4qe2 Ra4rU7 tu7ra7 se6vu9 zy5ka2 dy2xa6 je4qe3 xa7ve8 wu2fu8 ge2jy7 fu5mu8 gu4da5 ne4qa8 jy8fa8 cu3zy2 da3tu4 du8gu2 ka9pe5 ny5ba3 pa3by3 qe3je5 qy8du8 ta4he3 tu9wu9 ve8qu8 vu8ty2 we9wy4 qa6gy2 ma6jy3 ty7ne2 je6fe7 ne7su6 na8be3 wa8py6 jy5mu3 qa2ty5 ny5ry8 fu7ry8 pu6wu7 cE9Re8 nu5je7 vy3wu3 zu9cu5 xe9he5 cu5NE8 ty9ja7 cy9ju9 qa8qu5 ta9dy6 ny5py2 ve8dy2 da4ca4 hy5gy6 ja9dy8 ke4na7 ne5xa7 he4su3 ve2hu9 xa7ca3 da5ge6 xe2ky3 Cu5kU7 du4hu7 hu5te5 jy3wy4 qy8we6 wu5qe3 va5me9 by6te4 ke6hu7 ny3py2 py7xe3 ru3pa6 hy7mu6 ba8za5 ka2qy6 ry7na5 ta2we7 vu2hu7 fu7py6 ky2hu6 du2ky6 ga4ce9 su3ja5 zy8mu5 he4ku5 zy6xy5 be3vy9 gu3ry7 qu7xu5 cu5py6 dy2zy5 fe9ce2 wu9ce2 ka4he6 ra3we3 ra9by9 ze4hy2 mu8by3 wa6pe9 ma7gu6 ce9me6 qy9cy4 ra9va2 re7xe2 xy3ky4 qa2xy2 zy3ne4 xa7ta7 jy3fy8 ty6ta9 hy9za5 nu6by2 pu3ky9 cy8ce5 me5re7 he6ce4 ga5ha5 ne6vy7 te8xa5 ve9pu6 by3xa9 fa5fu6 tu9te6 za4gu3 ce6ky3 ju2cu9 be6ka2 sa4dy7 ge3ge2 py3qy2 xa4da8 ne5jy7 wu2wu8 xe3qe9 tu4ce7 xa7nu7 dy3hy9 xa3zu4 jy8py9 ta7fa3 ma2ka7 pa7gu6 fe2sy8 ga8ze7 ku7pa6 ky2ka6 ne6ju7 pu3ky5 pu6ga6 qa3su4 sa4ba4 su6jy6 za8xe7 ze9FY5 ra9hu5 va4gu8 dy8ne3 pe2my3 hy7qy9 ze9pe9 gu9za5 fy3bu8 su7re6 vy4fu8 du5xy9 qu6ka8 je9qu3 ba5wa5 wa6fu2 ze5xa2 he4py5 ge3da6 ty6ta6 ze4we9 ga7ve5 sy9mu4 my2su2 zu5fe8 gu9su2 ha7pa6 ka7dy2 qu6mu9 fy5ky8 re9ke9 ta9ky9 mE2rA2 se8fe8 ta9ny5 pe8he5 va4pu9 he7xa8 mu7ke4 fy3re9 hu7ba7 hy6ce6 qe4su7 ra2cu4 va3mu8 wa7he5 xa9su5 zy8be8 by3wy7 ra6de9 xy9qa4 ge4fe7 ra7je7 ne3my7 ru3gu8 ja3he5 pe7ha6 za4cy4 qu6xa4 su4je4 jy3fa7 sy5tu9 ry4na5 by7fe3 ca7ga4 wa6ce6 ha9ta5 ju5gu7 my3ju5 ca6xa5 ku3we4 pa9vu5 qe4ru4 ze9ka3 xa5my2 te3ja7 re7ga2 qy2ge3 ce5py2 ju8ja6 qy9re6 dy9ty8 re4hu8 me6zy8 bu4fu5 hu3je9 ja5re8 Ju4Qe6 me3ju6 mu6be7 qe9ra2 ru9fa8 te8ka3 vu2cy2 wu3ny4 pu8na7 nu4vu6 pa3de3 gA4Ry2 nE7Qu5 se8xe8 tu4jy4 ky5du9 ty7ga4 xy5jy4 fu7fy9 ra4du5 zu2fe2 da6ca4 xe7hu5 ce5wy9 ty9DE6 pa2bu8 ja3fe7 qu8da9 ty8jy7 fy2ha9 de4gu6 fe9cy8 fu6fa4 ge3wa3 ha9ga2 na5hy7 Qy6dA3 ru4gu4 se8we4 tu3cu4 re7gy3 ja9na5 ku4ca2 ra6ma8 cy8na8 xy5te8 ja5du5 pu8qy9 be6ma4 ce7xe3 sa9qu8 fa7su6 zu5xe4 xu6ra9 ce8dy4 my9ha4 NE2du2 qa4se3 qe9ga3 xa5de6 xu8qe9 xy4zu5 xy9su4 zy4ha4 jy9he6 xu8by7 my7ta2 bu3pe2 du3ja4 hy5pu9 pe7ga7 ry5qu7 se9ke6 tu2ne5 vu8fu6 wy9sy4 ha2ke8 ju5we3 ta8we8 ma8hu8 he8qe2 ca5pu9 fa2wa6 gu7te8 gy2mu4 na8ke4 pu5ny3 qu2ke8 su6ga2 we2sy5 by7re9 va2ca9 ve9we4 ba2ju3 ba4jy4 be2pa2 bu4re9 bu9da7 bu9ge9 by3zu8 by5qe4 by5ty3 by7be6 ca3bu3 ca6ne3 cy9mu2 da3cy7 du5pe4 du5vu3 du7tu7 dy9my4 fa6te2 fa8mu7 fe3be9 fe5zu9 fy3ze8 ga2cy2 ga2mu6 ga9ca4 ga9xa7 ge8gy6 gy6ja6 gy7my4 ha9mu9 ha9ny9 hu8ky2 hy4de9 ja9sy9 je7je3 je7jy4 je7wa4 jy2xy2 ka5hy6 ka6ma4 ku5sa3 ky9me7 ky9pu9 ma7he9 ma7se5 me8we4 my8qu9 na4we9 ne4by7 ne6ne5 ne9je9 ny9wa2 pa9ny6 pe7sa4 pu6zu3 py2qe8 py8qe6 qa6re2 qe7su7 qu3za8 qy7wu2 qy9gy6 re3se9 ru5sy9 ry5zu9 sa2we9 su4ty6 sy2se7 sy3ve4 ta3te8 ta9sy9 te5cu5 te9be9 va3tu7 vu8by2 vy3xe8 wY6mY8 wy9xy2 xa3ju9 xe5ty4 xe9ha3 xu8me6 xy2vy8 xy7ju7 xy7zy8 my8va3 ce9ju4 mu3se8 xy5ne6 sa5ge9 fa9be6 ze9cy4 za3vu7 qe3su7 ra9ru3 my6fa6 sa8de3 cu9ta6 fy2we9 na3je3 ja4ku2 ge4wa9 ge4sy7 xy5ja9 pu6ju2 ha3zy8 hy4qy8 hy4pu3 wy3my8 wu4xu2 ga6ce6
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
