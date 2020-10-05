import sqlite3
import re
import pyperclip

NLIST = 4
NLEVEL = 'п'

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
    where (u.type = 1 and token not like 'pass%') and p.lesson = :NLIST and p.level = :NLEVEL
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
order = 'cy3qe7 gu6ju5 nu4te3 qe9qe3 tu9hy5 vy4ga5 hu7ka2 ry7ca6 fu3cu3 nu2pu8 ja2xu9 na7xa7 va3ve2 wa2vu5 ce6du5 dy3ke6 fa2fa8 sa9pu8 ze8ry8 su5xu3 ve6fy3 ve9ju6 ca8gy3 fy2pu8 ga3ga8 nu8gu3 pe6ry6 qa3gy6 vy7tu2 zy4su3 he5ha9 ca5he9 cy2fa9 du5mu4 fy6ky6 mu7fe4 qy5ra2 qy7ru8 re5ha2 ve7ry6 hy3ny5 je8pa7 ke6wa3 qu8da5 su8ge4 sy9du2 ta9ra6 we3fu7 zy4he3 fe8jy5 fu3ku4 hu3ru7 ja4we4 my4me4 sy2zy4 ga5ne8 hy8du6 ja5pu7 ku7te7 nu9cu9 pe8qa4 wu3wu5 ge2jy7 ge4va5 qY2Ry8 qy5cu5 ry5vu4 su5ma6 vu8zu6 nu5ky2 py4ra2 xa6vu7 fu7ry8 ru4qe9 za8he8 zu2re8 da4he7 dy3zy3 gu5xu8 ky4ka7 su9sa3 ty9je5 vu4gu9 wu2fu8 xe9fu9 ce9ba9 gu5we5 gu6ja7 hy9ky3 ne7xy9 qu8ze7 za5ca8 fe5ke9 hy5gy6 ny2ma2 fe2zu2 gy8ra8 he4ba3 jy4ra2 pa9ce6 qa3ce9 sa7pu5 ty7ne6 va5su2 xu5se2 xu6ja6 fa3na2 fu5mu8 gu4da5 he6su5 he7xe9 ja9dy8 my7za8 ne4qa8 py8ce5 qa5sa6 te7gu5 va7xu6 xu9wu9 xy3vu3 be4be3 fa4fy7 fy3ka8 ky6hy6 mu5su4 Qa4Da2 se6vu9 va5me9 vu7qu9 cy9ju9 cy5ca7 jy8fa8 ny2jy9 pe2sy8 qa8qu5 qu9me3 za4fy8 zy5ka2 be7ce2 by6te4 dy7we7 je6fe7 ke4na7 ku4qe5 ne5xa7 ne7su6 pe5su6 pu3ky9 ra9by9 sy8sy5 ve2ze3 vU3xY2 za9ra2 zy4py4 cu3zy2 he4su3 ke6hu7 na8be3 nu9we6 qe4qu4 ta9dy6 vu4ve5 wa8py6 he4ku5 nu6by2 sy5xy5 ve2hu9 be3vy9 cE9Re8 da3tu4 gu3ry7 ha7ja2 jy4qe2 jy5mu3 nu5je7 qa2ty5 qe2ja8 Ra4rU7 tu7ra7 vy3wu3 ze4hy2 zu9cu5 ba8za5 cy8ce5 du8gu2 ka9pe5 me3re4 ny3py2 ny5ba3 ny5py2 pa3by3 qe3je5 qu7xu5 qy8du8 ta4he3 tu9wu9 ve8dy2 ve8qu8 vu8ty2 we9wy4 xa7ca3 xe9he5 xy3ky4 be3fy6 cu5NE8 cu5py6 da5fa7 dy2xa6 dy2zy5 je4qe3 me5re7 mu8by3 pu6wu7 py7xe3 qa6gy2 ta2we7 vu2hu7 fa5fu6 by9ru9 da4ca4 da5ge6 ju2cu9 ru3pa6 tu4ce7 wa6pe9 xa7nu7 xa7ve8 xe2ky3 be6ka2 bu8vu2 Cu5kU7 du4hu7 dy3hy9 fe9ce2 fu7py6 hu5te5 jy3wy4 ka2qy6 ky2hu6 qa2xy2 qy8we6 wu5qe3 wu9ce2 xa3zu4 he6ce4 ka4he6 sa4dy7 zy3ne4 du2ky6 ga4ce9 su3ja5 zy8mu5 ge3ge2 hy7mu6 ma7gu6 ny5ry8 ty9ja7 zy6xy5 ce6ky3 ce9me6 gu9za5 jy8py9 py3qy2 qu6xa4 qy9cy4 ra3we3 ra9va2 re7xe2 ry7na5 ta7fa3 vy4fu8 xa4da8 xa7ta7 du5xy9 jy3fy8 ma2ka7 ne5jy7 pa7gu6 qu6ka8 re9ke9 ta9ky9 ty6ta9 wu2wu8 by3xa9 ga5ha5 ju5gu7 ne6vy7 te8xa5 ve9pu6 dy8ne3 hy9za5 je9qu3 pe2my3 tu9te6 za4gu3 ba5wa5 cy8na8 fe2sy8 gA4Ry2 ga8ze7 ku7pa6 ky2ka6 mE2rA2 my3ju5 ne6ju7 pu3ky5 pu6ga6 qa3su4 ra7je7 re4hu8 sa4ba4 se8fe8 su4je4 su6jy6 ta9ny5 wa6fu2 za8xe7 ze5xa2 ze9FY5 fy3bu8 he4py5 hy7qy9 jy3fa7 ne3my7 pe8he5 ra9hu5 ru3gu8 su7re6 sy5tu9 te3ja7 xa5my2 ca6xa5 ge3da6 ty6ta6 va4pu9 za4cy4 ze4we9 ga7ve5 ge4fe7 he7xa8 ja3he5 me6zy8 mu7ke4 my2su2 re7ga2 ry4na5 zu5fe8 by7fe3 ca7ga4 fy3re9 gu9su2 ha7pa6 hu7ba7 hy6ce6 ka7dy2 ma6jy3 nE7Qu5 qe4su7 qu6mu9 qy2ge3 ra2cu4 sy9mu4 va3mu8 wa6ce6 wa7he5 xa9su5 xe3qe9 ze9pe9 zy8be8 ce5py2 fy5ky8 ha9ta5 ju8ja6 xe7hu5 bu4fu5 by3wy7 pa2bu8 ku3we4 nu4vu6 pa9vu5 qe4ru4 qy9re6 dy9ty8 hu3je9 ja3fe7 ja5re8 Ju4Qe6 me3ju6 mu6be7 pa3de3 pe7ha6 qe9ra2 qu8da9 ru9fa8 se8xe8 te8ka3 tu4jy4 ty8jy7 vu2cy2 wu3ny4 xy5te8 ze9ka3 fu7fy9 ky5du9 ty7ga4 xy5jy4 ra4du5 ra6de9 zu2fe2 ce5wy9 fy2ha9 ty9DE6 da6ca4 de4gu6 fa7su6 fe9cy8 fu6fa4 ge3wa3 ha9ga2 ku4ca2 na5hy7 pu8na7 Qy6dA3 ru4gu4 se8we4 tu3cu4 xu6ra9 zu5xe4 ja5du5 pu8qy9 re7gy3 be6ma4 ce7xe3 ce8dy4 jy9he6 my9ha4 NE2du2 qa4se3 qe9ga3 ra6ma8 sa9qu8 xa5de6 xu8by7 xu8qe9 xy4zu5 xy9su4 zy4ha4 my7ta2 bu3pe2 du3ja4 hy5pu9 ma8hu8 pe7ga7 ry5qu7 se9ke6 tu2ne5 vu8fu6 wy9sy4 ca5pu9 fa2wa6 gu7te8 gy2mu4 he8qe2 na8ke4 pu5ny3 qu2ke8 su6ga2 we2sy5 va2ca9 ve9we4 ba2ju3 ba4jy4 be2pa2 bu4re9 bu9da7 bu9ge9 by3zu8 by5qe4 by5ty3 by7be6 by7re9 ca3bu3 ca6ne3 cy9mu2 da3cy7 du5pe4 du5vu3 du7tu7 dy9my4 fa6te2 fa8mu7 fe3be9 fe5zu9 fy3ze8 ga2cy2 ga2mu6 ga9ca4 ga9xa7 ge8gy6 gy6ja6 gy7my4 ha2ke8 ha9mu9 ha9ny9 hu8ky2 hy4de9 ja9na5 ja9sy9 je7je3 je7jy4 je7wa4 ju5we3 jy2xy2 ka5hy6 ka6ma4 ku5sa3 ky9me7 ky9pu9 ma7he9 ma7se5 me8we4 my8qu9 na4we9 ne4by7 ne6ne5 ne9je9 ny9wa2 pa9ny6 pe7sa4 pu6zu3 py2qe8 py8qe6 qa6re2 qe7su7 qu2qe9 qu3za8 qy7wu2 qy9gy6 re3se9 ru5sy9 ry5zu9 sa2we9 su4ty6 sy2se7 sy3ve4 ta3te8 ta8we8 ta9sy9 te5cu5 te9be9 ty7ne2 va3tu7 va4gu8 vu8by2 vy3xe8 wY6mY8 wy9xy2 xa3ju9 xe5ty4 xe9ha3 xu8me6 xy2vy8 xy7ju7 xy7zy8 xy9qa4'
ordered_pupils = [token_to_pupil[token] for token in order.split()]
pupils = ordered_pupils






cur.execute('''
    select p.lesson || p.level || '.' || p.prob  || p.item as prob
    from problems p
    where p.lesson = :NLIST and p.level = :NLEVEL
''', globals())
problems = set({x[0] for x in cur.fetchall()})

formated_problems = []
for problem in problems:
    m = re.fullmatch('(\d+)([а-я])\.(\d+)([а-я]?)', problem)
    lst, lvl, prb, itm = m.groups()
    formated_problems.append((f'{int(lst):02}{lvl}.{int(prb):02}{itm}', problem))
formated_problems.sort()
table = [[''] * (len(problems) + 1) for __ in range(len(pupils) + 1)]
table[0][0] = 'token\tФамилия\tИмя\tнач/прод'
for c, (formatted, problem) in enumerate(formated_problems, start=1):
    table[0][c] = formatted
for r, pupil in enumerate(pupils, start=1):
    table[r][0] = pupil


for r, pupil in enumerate(ordered_pupils, start=1):
    for c, (formatted, problem) in enumerate(formated_problems, start=1):
        table[r][c] = results.get((pupil, problem), '')

stable = '\n'.join('\t'.join(row[1:]) for row in table)
pyperclip.copy(stable)
print(stable)
