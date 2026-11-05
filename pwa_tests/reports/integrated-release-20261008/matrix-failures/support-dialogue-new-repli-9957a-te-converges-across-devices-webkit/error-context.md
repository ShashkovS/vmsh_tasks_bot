# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: support-dialogue.spec.ts >> new replies jump into an older worksheet and read state converges across devices
- Location: e2e/support-dialogue.spec.ts:123:1

# Error details

```
Error: page.goto: Navigation to "http://127.0.0.1:5380/student/tasks?course=math-5-7&group=%D0%BD&question=sup-4" is interrupted by another navigation to "http://127.0.0.1:5380/student/profile"
Call log:
  - navigating to "http://127.0.0.1:5380/student/tasks?course=math-5-7&group=%D0%BD&question=sup-4", waiting until "load"

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - banner [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]:
          - link "ВМШ 179" [ref=e7]:
            - /url: /student/
            - generic [ref=e8]:
              - img [ref=e9]:
                - generic [ref=e12]: "179"
              - generic [ref=e13]: ВМШ 179
          - generic "Алексей Тестовый-Онлайн" [ref=e14]
        - button "Переключить на тёмную тему" [ref=e16]:
          - img
    - generic [ref=e17]:
      - complementary [ref=e18]:
        - navigation "Основная навигация" [ref=e19]:
          - link "Сейчас" [ref=e20]:
            - /url: /student/
            - img [ref=e21]
            - generic [ref=e24]: Сейчас
          - link "Задачи" [ref=e25]:
            - /url: /student/tasks
            - img [ref=e26]
            - generic [ref=e28]: Задачи
          - link "Новости" [ref=e29]:
            - /url: /student/news
            - img [ref=e30]
            - generic [ref=e33]: Новости
          - link "Прогресс" [ref=e34]:
            - /url: /student/progress
            - img [ref=e35]
            - generic [ref=e38]: Прогресс
          - link "Профиль" [ref=e39]:
            - /url: /student/profile
            - img [ref=e40]
            - generic [ref=e43]: Профиль
      - main [ref=e44]:
        - status [ref=e45]: Задачи всех уровней сохранены
        - generic [ref=e47]:
          - group "Группа курса «Математика 5–7»" [ref=e48]:
            - generic [ref=e49]: Группа курса «Математика 5–7»
            - generic [ref=e50]:
              - button "Начинающие" [pressed] [ref=e51]:
                - generic [ref=e52]:
                  - generic [ref=e53]: н
                  - text: Начинающие
              - button "Продолжающие" [ref=e54]:
                - generic [ref=e55]:
                  - generic [ref=e56]: п
                  - text: Продолжающие
              - button "Эксперты" [ref=e57]:
                - generic [ref=e58]:
                  - generic [ref=e59]: э
                  - text: Эксперты
          - generic [ref=e60]:
            - generic [ref=e61]:
              - generic [ref=e64]:
                - generic [ref=e65]:
                  - generic [ref=e66]:
                    - generic [ref=e67]:
                      - paragraph [ref=e68]: Занятие 34103 · 29 июля
                      - generic [ref=e69]: Устная E2E firefox
                    - generic [ref=e70]:
                      - generic [ref=e71]: Только условие
                      - button "Ответить на все задачи" [ref=e72]
                  - paragraph [ref=e73]:
                    - img [ref=e74]
                    - text: 1 задача в листке
                - article [ref=e76]:
                  - generic [ref=e77]:
                    - paragraph [ref=e78]: "Общее введение для разбора: обосновывайте каждый переход."
                    - region "Задача 34103н.1. «Устная E2E firefox»" [ref=e79]:
                      - generic [ref=e80]:
                        - heading "Задача 34103н.1. «Устная E2E firefox»" [level=2] [ref=e81]:
                          - text: Задача 34103н.1.
                          - generic [ref=e82]: «Устная E2E firefox»
                        - generic [ref=e83]:
                          - generic [ref=e84]: Не начата
                          - button "Открыть задачу 1" [ref=e85]:
                            - text: Открыть
                            - img
                      - paragraph [ref=e86]: Найдите площадь треугольника ABC. Объясните своё решение.
                      - paragraph [ref=e87]:
                        - generic [ref=e90]:
                          - math [ref=e92]:
                            - generic [ref=e93]:
                              - generic [ref=e94]:
                                - generic [ref=e95]: S
                                - generic [ref=e96]: =
                                - generic [ref=e97]:
                                  - generic [ref=e98]:
                                    - generic [ref=e99]: a
                                    - generic [ref=e100]: h
                                  - generic [ref=e101]: "2"
                              - generic: "S=\\frac{ah}{2}"
                          - generic [ref=e102]:
                            - generic [ref=e103]: S =
                            - generic [ref=e109]:
                              - generic [ref=e111]: "2"
                              - generic [ref=e114]: ah
                      - figure "Рис. 1. Треугольник ABC." [ref=e118]:
                        - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e120] [cursor=pointer]':
                          - img "Треугольник ABC" [ref=e121]
                        - generic [ref=e122]: Рис. 1. Треугольник ABC.
                      - figure "Рис. 2. Цвета сохраняются." [ref=e123]:
                        - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e125] [cursor=pointer]':
                          - img "Цветной прямоугольник" [ref=e126]
                        - generic [ref=e127]: Рис. 2. Цвета сохраняются.
                      - generic [ref=e130]:
                        - button "Ответить" [ref=e131]:
                          - img
                          - text: Ответить
                          - img
                        - region "Обсуждение задачи" [ref=e132]:
                          - button "Задать вопрос" [ref=e133]:
                            - img
                            - text: Задать вопрос
                    - region "Задача 34103н.2. «Длинная задача с пунктами»" [ref=e134]:
                      - heading "Задача 34103н.2. «Длинная задача с пунктами»" [level=2] [ref=e136]:
                        - text: Задача 34103н.2.
                        - generic [ref=e137]: «Длинная задача с пунктами»
                      - generic [ref=e138]:
                        - strong [ref=e140]:
                          - text: 2а)
                          - generic [ref=e141]: «Рассуждение»
                        - generic [ref=e142]:
                          - paragraph [ref=e143]: Шаг 1. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e144]: Шаг 2. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e145]: Шаг 3. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e146]: Шаг 4. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e147]: Шаг 5. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e148]: Шаг 6. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e149]: Шаг 7. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e150]: Шаг 8. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e151]: Шаг 9. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e152]: Шаг 10. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e153]: Шаг 11. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e154]: Шаг 12. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e155]: Шаг 13. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e156]: Шаг 14. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e157]: Шаг 15. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e158]: Шаг 16. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e159]: Шаг 17. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e160]: Шаг 18. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e161]: Шаг 19. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e162]: Шаг 20. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e163]: Шаг 21. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e164]: Шаг 22. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e165]: Шаг 23. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e166]: Шаг 24. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                      - generic [ref=e167]:
                        - strong [ref=e169]:
                          - text: 2б)
                          - generic [ref=e170]: «Чертёж ниже экрана»
                        - generic [ref=e171]:
                          - paragraph [ref=e172]: Проверьте полученный результат по чертежу.
                          - figure "Рис. 1. Треугольник ABC." [ref=e173]:
                            - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e175] [cursor=pointer]':
                              - img "Треугольник ABC" [ref=e176]
                            - generic [ref=e177]: Рис. 1. Треугольник ABC.
                          - generic [ref=e182]:
                            - math [ref=e184]:
                              - generic [ref=e185]:
                                - generic [ref=e186]:
                                  - generic [ref=e187]:
                                    - generic [ref=e188]: a
                                    - generic [ref=e189]: "2"
                                  - generic [ref=e190]: +
                                  - generic [ref=e191]:
                                    - generic [ref=e192]: b
                                    - generic [ref=e193]: "2"
                                  - generic [ref=e194]: =
                                  - generic [ref=e195]:
                                    - generic [ref=e196]: c
                                    - generic [ref=e197]: "2"
                                - generic: a^2+b^2=c^2
                            - generic [ref=e198]:
                              - generic [ref=e199]:
                                - generic [ref=e200]:
                                  - text: a
                                  - generic [ref=e205]: "2"
                                - text: +
                              - generic [ref=e206]:
                                - generic [ref=e207]:
                                  - text: b
                                  - generic [ref=e212]: "2"
                                - text: =
                              - generic [ref=e214]:
                                - text: c
                                - generic [ref=e219]: "2"
              - generic [ref=e222]:
                - generic [ref=e223]:
                  - generic [ref=e224]:
                    - generic [ref=e225]:
                      - paragraph [ref=e226]: Занятие 34102 · 29 июля
                      - generic [ref=e227]: Устная E2E webkit
                    - generic [ref=e228]:
                      - generic [ref=e229]: Только условие
                      - button "Ответить на все задачи" [ref=e230]
                  - paragraph [ref=e231]:
                    - img [ref=e232]
                    - text: 1 задача в листке
                - article [ref=e234]:
                  - generic [ref=e235]:
                    - paragraph [ref=e236]: "Общее введение для разбора: обосновывайте каждый переход."
                    - region "Задача 34102н.1. «Устная E2E webkit»" [ref=e237]:
                      - generic [ref=e238]:
                        - heading "Задача 34102н.1. «Устная E2E webkit»" [level=2] [ref=e239]:
                          - text: Задача 34102н.1.
                          - generic [ref=e240]: «Устная E2E webkit»
                        - generic [ref=e241]:
                          - generic [ref=e242]: Не начата
                          - button "Открыть задачу 1" [ref=e243]:
                            - text: Открыть
                            - img
                      - paragraph [ref=e244]: Найдите площадь треугольника ABC. Объясните своё решение.
                      - paragraph [ref=e245]:
                        - generic [ref=e248]:
                          - math [ref=e250]:
                            - generic [ref=e251]:
                              - generic [ref=e252]:
                                - generic [ref=e253]: S
                                - generic [ref=e254]: =
                                - generic [ref=e255]:
                                  - generic [ref=e256]:
                                    - generic [ref=e257]: a
                                    - generic [ref=e258]: h
                                  - generic [ref=e259]: "2"
                              - generic: "S=\\frac{ah}{2}"
                          - generic [ref=e260]:
                            - generic [ref=e261]: S =
                            - generic [ref=e267]:
                              - generic [ref=e269]: "2"
                              - generic [ref=e272]: ah
                      - figure "Рис. 1. Треугольник ABC." [ref=e276]:
                        - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e278] [cursor=pointer]':
                          - img "Треугольник ABC" [ref=e279]
                        - generic [ref=e280]: Рис. 1. Треугольник ABC.
                      - figure "Рис. 2. Цвета сохраняются." [ref=e281]:
                        - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e283] [cursor=pointer]':
                          - img "Цветной прямоугольник" [ref=e284]
                        - generic [ref=e285]: Рис. 2. Цвета сохраняются.
                      - generic [ref=e288]:
                        - button "Ответить" [ref=e289]:
                          - img
                          - text: Ответить
                          - img
                        - region "Обсуждение задачи" [ref=e290]:
                          - button "Задать вопрос" [ref=e291]:
                            - img
                            - text: Задать вопрос
                    - region "Задача 34102н.2. «Длинная задача с пунктами»" [ref=e292]:
                      - heading "Задача 34102н.2. «Длинная задача с пунктами»" [level=2] [ref=e294]:
                        - text: Задача 34102н.2.
                        - generic [ref=e295]: «Длинная задача с пунктами»
                      - generic [ref=e296]:
                        - strong [ref=e298]:
                          - text: 2а)
                          - generic [ref=e299]: «Рассуждение»
                        - generic [ref=e300]:
                          - paragraph [ref=e301]: Шаг 1. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e302]: Шаг 2. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e303]: Шаг 3. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e304]: Шаг 4. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e305]: Шаг 5. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e306]: Шаг 6. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e307]: Шаг 7. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e308]: Шаг 8. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e309]: Шаг 9. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e310]: Шаг 10. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e311]: Шаг 11. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e312]: Шаг 12. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e313]: Шаг 13. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e314]: Шаг 14. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e315]: Шаг 15. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e316]: Шаг 16. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e317]: Шаг 17. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e318]: Шаг 18. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e319]: Шаг 19. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e320]: Шаг 20. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e321]: Шаг 21. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e322]: Шаг 22. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e323]: Шаг 23. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e324]: Шаг 24. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                      - generic [ref=e325]:
                        - strong [ref=e327]:
                          - text: 2б)
                          - generic [ref=e328]: «Чертёж ниже экрана»
                        - generic [ref=e329]:
                          - paragraph [ref=e330]: Проверьте полученный результат по чертежу.
                          - figure "Рис. 1. Треугольник ABC." [ref=e331]:
                            - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e333] [cursor=pointer]':
                              - img "Треугольник ABC" [ref=e334]
                            - generic [ref=e335]: Рис. 1. Треугольник ABC.
                          - generic [ref=e340]:
                            - math [ref=e342]:
                              - generic [ref=e343]:
                                - generic [ref=e344]:
                                  - generic [ref=e345]:
                                    - generic [ref=e346]: a
                                    - generic [ref=e347]: "2"
                                  - generic [ref=e348]: +
                                  - generic [ref=e349]:
                                    - generic [ref=e350]: b
                                    - generic [ref=e351]: "2"
                                  - generic [ref=e352]: =
                                  - generic [ref=e353]:
                                    - generic [ref=e354]: c
                                    - generic [ref=e355]: "2"
                                - generic: a^2+b^2=c^2
                            - generic [ref=e356]:
                              - generic [ref=e357]:
                                - generic [ref=e358]:
                                  - text: a
                                  - generic [ref=e363]: "2"
                                - text: +
                              - generic [ref=e364]:
                                - generic [ref=e365]:
                                  - text: b
                                  - generic [ref=e370]: "2"
                                - text: =
                              - generic [ref=e372]:
                                - text: c
                                - generic [ref=e377]: "2"
              - generic [ref=e380]:
                - generic [ref=e381]:
                  - generic [ref=e382]:
                    - generic [ref=e383]:
                      - paragraph [ref=e384]: Занятие 34101 · 29 июля
                      - generic [ref=e385]: Устная E2E chromium
                    - generic [ref=e386]:
                      - generic [ref=e387]: Только условие
                      - button "Ответить на все задачи" [ref=e388]
                  - paragraph [ref=e389]:
                    - img [ref=e390]
                    - text: 1 задача в листке
                - article [ref=e392]:
                  - generic [ref=e393]:
                    - paragraph [ref=e394]: "Общее введение для разбора: обосновывайте каждый переход."
                    - region "Задача 34101н.1. «Устная E2E chromium»" [ref=e395]:
                      - generic [ref=e396]:
                        - heading "Задача 34101н.1. «Устная E2E chromium»" [level=2] [ref=e397]:
                          - text: Задача 34101н.1.
                          - generic [ref=e398]: «Устная E2E chromium»
                        - generic [ref=e399]:
                          - generic [ref=e400]: Не начата
                          - button "Открыть задачу 1" [ref=e401]:
                            - text: Открыть
                            - img
                      - paragraph [ref=e402]: Найдите площадь треугольника ABC. Объясните своё решение.
                      - paragraph [ref=e403]:
                        - generic [ref=e406]:
                          - math [ref=e408]:
                            - generic [ref=e409]:
                              - generic [ref=e410]:
                                - generic [ref=e411]: S
                                - generic [ref=e412]: =
                                - generic [ref=e413]:
                                  - generic [ref=e414]:
                                    - generic [ref=e415]: a
                                    - generic [ref=e416]: h
                                  - generic [ref=e417]: "2"
                              - generic: "S=\\frac{ah}{2}"
                          - generic [ref=e418]:
                            - generic [ref=e419]: S =
                            - generic [ref=e425]:
                              - generic [ref=e427]: "2"
                              - generic [ref=e430]: ah
                      - figure "Рис. 1. Треугольник ABC." [ref=e434]:
                        - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e436] [cursor=pointer]':
                          - img "Треугольник ABC" [ref=e437]
                        - generic [ref=e438]: Рис. 1. Треугольник ABC.
                      - figure "Рис. 2. Цвета сохраняются." [ref=e439]:
                        - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e441] [cursor=pointer]':
                          - img "Цветной прямоугольник" [ref=e442]
                        - generic [ref=e443]: Рис. 2. Цвета сохраняются.
                      - generic [ref=e446]:
                        - button "Ответить" [ref=e447]:
                          - img
                          - text: Ответить
                          - img
                        - region "Обсуждение задачи" [ref=e448]:
                          - button "Задать вопрос" [ref=e449]:
                            - img
                            - text: Задать вопрос
                    - region "Задача 34101н.2. «Длинная задача с пунктами»" [ref=e450]:
                      - heading "Задача 34101н.2. «Длинная задача с пунктами»" [level=2] [ref=e452]:
                        - text: Задача 34101н.2.
                        - generic [ref=e453]: «Длинная задача с пунктами»
                      - generic [ref=e454]:
                        - strong [ref=e456]:
                          - text: 2а)
                          - generic [ref=e457]: «Рассуждение»
                        - generic [ref=e458]:
                          - paragraph [ref=e459]: Шаг 1. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e460]: Шаг 2. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e461]: Шаг 3. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e462]: Шаг 4. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e463]: Шаг 5. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e464]: Шаг 6. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e465]: Шаг 7. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e466]: Шаг 8. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e467]: Шаг 9. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e468]: Шаг 10. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e469]: Шаг 11. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e470]: Шаг 12. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e471]: Шаг 13. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e472]: Шаг 14. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e473]: Шаг 15. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e474]: Шаг 16. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e475]: Шаг 17. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e476]: Шаг 18. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e477]: Шаг 19. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e478]: Шаг 20. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e479]: Шаг 21. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e480]: Шаг 22. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e481]: Шаг 23. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                          - paragraph [ref=e482]: Шаг 24. Проведите высоту из вершины A и рассмотрите два прямоугольных треугольника. Докажите равенство площадей и запишите вывод.
                      - generic [ref=e483]:
                        - strong [ref=e485]:
                          - text: 2б)
                          - generic [ref=e486]: «Чертёж ниже экрана»
                        - generic [ref=e487]:
                          - paragraph [ref=e488]: Проверьте полученный результат по чертежу.
                          - figure "Рис. 1. Треугольник ABC." [ref=e489]:
                            - 'button "Нажмите, чтобы изменить размер рисунка: 100%." [ref=e491] [cursor=pointer]':
                              - img "Треугольник ABC" [ref=e492]
                            - generic [ref=e493]: Рис. 1. Треугольник ABC.
                          - generic [ref=e498]:
                            - math [ref=e500]:
                              - generic [ref=e501]:
                                - generic [ref=e502]:
                                  - generic [ref=e503]:
                                    - generic [ref=e504]: a
                                    - generic [ref=e505]: "2"
                                  - generic [ref=e506]: +
                                  - generic [ref=e507]:
                                    - generic [ref=e508]: b
                                    - generic [ref=e509]: "2"
                                  - generic [ref=e510]: =
                                  - generic [ref=e511]:
                                    - generic [ref=e512]: c
                                    - generic [ref=e513]: "2"
                                - generic: a^2+b^2=c^2
                            - generic [ref=e514]:
                              - generic [ref=e515]:
                                - generic [ref=e516]:
                                  - text: a
                                  - generic [ref=e521]: "2"
                                - text: +
                              - generic [ref=e522]:
                                - generic [ref=e523]:
                                  - text: b
                                  - generic [ref=e528]: "2"
                                - text: =
                              - generic [ref=e530]:
                                - text: c
                                - generic [ref=e535]: "2"
              - generic [ref=e538]:
                - generic [ref=e539]:
                  - generic [ref=e540]:
                    - generic [ref=e541]:
                      - paragraph [ref=e542]: Занятие 33103 · 29 июля
                      - generic [ref=e543]: Устная E2E firefox
                    - generic [ref=e545]: Только условие
                  - paragraph [ref=e546]:
                    - img [ref=e547]
                    - text: 1 задача в листке
                - article [ref=e549]:
                  - region "Задача 33103н.1. «Устная E2E firefox»" [ref=e551]:
                    - generic [ref=e552]:
                      - heading "Задача 33103н.1. «Устная E2E firefox»" [level=2] [ref=e553]:
                        - text: Задача 33103н.1.
                        - generic [ref=e554]: «Устная E2E firefox»
                      - generic [ref=e555]:
                        - generic [ref=e556]: Не начата
                        - button "Открыть задачу 1" [ref=e557]:
                          - text: Открыть
                          - img
                    - paragraph [ref=e558]: Расскажите решение преподавателю или отправьте его письменно.
                    - region "Обсуждение задачи" [ref=e562]:
                      - button "Задать вопрос" [ref=e563]:
                        - img
                        - text: Задать вопрос
              - generic [ref=e566]:
                - generic [ref=e567]:
                  - generic [ref=e568]:
                    - generic [ref=e569]:
                      - paragraph [ref=e570]: Занятие 33102 · 29 июля
                      - generic [ref=e571]: Устная E2E webkit
                    - generic [ref=e573]: Только условие
                  - paragraph [ref=e574]:
                    - img [ref=e575]
                    - text: 1 задача в листке
                - article [ref=e577]:
                  - region "Задача 33102н.1. «Устная E2E webkit»" [ref=e579]:
                    - generic [ref=e580]:
                      - heading "Задача 33102н.1. «Устная E2E webkit»" [level=2] [ref=e581]:
                        - text: Задача 33102н.1.
                        - generic [ref=e582]: «Устная E2E webkit»
                      - generic [ref=e583]:
                        - generic [ref=e584]: Не начата
                        - button "Открыть задачу 1" [ref=e585]:
                          - text: Открыть
                          - img
                    - paragraph [ref=e586]: Расскажите решение преподавателю или отправьте его письменно.
                    - region "Обсуждение задачи" [ref=e590]:
                      - button "Задать вопрос" [ref=e591]:
                        - img
                        - text: Задать вопрос
            - button "Показать более ранние занятия" [ref=e592]
  - generic:
    - region "Notifications"
```

# Test source

```ts
  123 | test('new replies jump into an older worksheet and read state converges across devices', async ({
  124 |   page,
  125 |   context,
  126 |   secondaryContext,
  127 | }, testInfo) => {
  128 |   test.setTimeout(120_000)
  129 |   const lesson = ({ chromium: 32101, webkit: 32102, firefox: 32103 } as Record<string, number>)[
  130 |     testInfo.project.name
  131 |   ]!
  132 |   await loginThroughUi(
  133 |     page,
  134 |     AUTH_PERSONAS.student,
  135 |     `/student/tasks/math-5-7/${encodeURIComponent('н')}/${lesson}`,
  136 |   )
  137 |   const question = page.getByRole('region', { name: 'Обсуждение задачи' }).first()
  138 |   await question.getByRole('button', { name: /^(Задать вопрос|Вопросы по задаче)/ }).click()
  139 |   await question
  140 |     .getByRole('textbox', { name: 'Сообщение' })
  141 |     .fill(`Вопрос attention ${testInfo.project.name} ${testInfo.retry}`)
  142 |   const created = page.waitForResponse(
  143 |     (r) =>
  144 |       r.request().method() === 'POST' &&
  145 |       /\/student\/api\/v1\/questions(?:\/sup-\d+\/entries)?$/.test(new URL(r.url()).pathname),
  146 |   )
  147 |   await question.getByRole('button', { name: /^(Отправить вопрос|Дополнить вопрос)$/ }).click()
  148 |   const threadId = ((await (await created).json()) as { thread: { threadId: string } }).thread
  149 |     .threadId
  150 |   await expect(question.getByRole('button', { name: 'Дополнить вопрос', exact: true })).toBeVisible(
  151 |     { timeout: 15_000 },
  152 |   )
  153 |   await expect(question.getByRole('button', { name: /Ждём ответа преподавателя/ })).toBeVisible({
  154 |     timeout: 15_000,
  155 |   })
  156 |   await question.getByRole('button', { name: 'Скрыть вопросы' }).click()
  157 | 
  158 |   const access = studentCourseAccessResponseSchema.parse(
  159 |     await (await page.request.get('/student/api/v1/courses')).json(),
  160 |   )
  161 |   const contexts = access.enrollments.flatMap((enrollment) =>
  162 |     enrollment.allowedGroups.map((group) => ({ enrollment, group })),
  163 |   )
  164 |   const another =
  165 |     contexts.find(({ enrollment }) => enrollment.course.code !== 'math-5-7') ??
  166 |     contexts.find(({ group }) => group.code !== 'н')
  167 |   expect(another, 'Fixture must exercise switching course/group').toBeDefined()
  168 |   if (process.env.VMSH_E2E_SUPPORT_NAVIGATION === '1')
  169 |     expect(another!.enrollment.course.code).not.toBe('math-5-7')
  170 |   await page.goto(
  171 |     `/student/tasks?course=${encodeURIComponent(another!.enrollment.course.code)}&group=${encodeURIComponent(another!.group.code)}`,
  172 |   )
  173 |   const device = await secondaryContext.newPage()
  174 |   await loginThroughUi(device, AUTH_PERSONAS.student, '/student/tasks')
  175 |   const staff = await context.newPage()
  176 |   await loginThroughUi(staff, AUTH_PERSONAS.teacher, `/staff/questions/${threadId}`)
  177 |   const text = `Новый ответ attention ${testInfo.project.name} ${testInfo.retry}`
  178 |   await staff.getByRole('textbox', { name: 'Сообщение' }).fill(text)
  179 |   await staff.getByRole('button', { name: 'Ответить', exact: true }).click()
  180 |   await expect(page.getByRole('button', { name: /Новые ответы \(/ })).toBeVisible()
  181 |   await expect(device.getByRole('button', { name: /Новые ответы \(/ })).toBeVisible()
  182 |   await page.bringToFront()
  183 |   await page.getByRole('button', { name: /Новые ответы \(/ }).click()
  184 |   await expect(page).toHaveURL(new RegExp(`question=${threadId}`))
  185 |   await expect(page.getByText(text, { exact: true })).toBeInViewport()
  186 |   const targetQuestion = page
  187 |     .getByRole('region', { name: 'Обсуждение задачи' })
  188 |     .filter({ hasText: text })
  189 |   await expect(
  190 |     targetQuestion.getByRole('button', { name: /Есть непрочитанный ответ/ }),
  191 |   ).toBeVisible()
  192 |   await targetQuestion
  193 |     .getByRole('button', { name: /Есть непрочитанный ответ/ })
  194 |     .screenshot({ path: testInfo.outputPath('question-unread-indicator.png') })
  195 |   await targetQuestion
  196 |     .locator('..')
  197 |     .screenshot({ path: testInfo.outputPath('question-unread.png') })
  198 |   await expect(page.getByRole('button', { name: /Новые ответы \(/ })).toHaveCount(0, {
  199 |     timeout: 15_000,
  200 |   })
  201 |   await expect(device.getByRole('button', { name: /Новые ответы \(/ })).toHaveCount(0, {
  202 |     timeout: 15_000,
  203 |   })
  204 |   await expect(
  205 |     targetQuestion.getByRole('button', { name: /Есть непрочитанный ответ/ }),
  206 |   ).toHaveCount(0)
  207 |   await page.reload()
  208 |   await expect(page.getByText(text, { exact: true })).toBeInViewport()
  209 |   await page.setViewportSize({ width: 320, height: 800 })
  210 |   await page.emulateMedia({ reducedMotion: 'reduce' })
  211 |   await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  212 |   await expect(page.getByRole('button', { name: 'Переключить на светлую тему' })).toBeVisible()
  213 |   await targetQuestion.locator('..').scrollIntoViewIfNeeded()
  214 |   await targetQuestion
  215 |     .locator('..')
  216 |     .screenshot({ path: testInfo.outputPath('question-read-dark-320.png') })
  217 |   const localeHeaders = { Origin: new URL(page.url()).origin }
  218 |   const answerUrl = page.url()
  219 |   try {
  220 |     await page.goto('/student/profile')
  221 |     await page.getByRole('radio', { name: 'English' }).click()
  222 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
> 223 |     await page.goto(answerUrl)
      |                ^ Error: page.goto: Navigation to "http://127.0.0.1:5380/student/tasks?course=math-5-7&group=%D0%BD&question=sup-4" is interrupted by another navigation to "http://127.0.0.1:5380/student/profile"
  224 |     const englishQuestion = page
  225 |       .getByRole('region', { name: 'Problem discussion', exact: true })
  226 |       .filter({ hasText: text })
  227 |     await englishQuestion.getByRole('button', { name: 'Hide questions', exact: true }).click()
  228 |     await staff.getByRole('textbox', { name: 'Сообщение' }).fill(`${text} EN`)
  229 |     await staff.getByRole('button', { name: 'Ответить', exact: true }).click()
  230 |     await expect(page.getByRole('button', { name: /New replies \(/ })).toBeVisible()
  231 |     await page.getByRole('button', { name: /New replies \(/ }).click()
  232 |     await expect(page.getByText(`${text} EN`, { exact: true })).toBeInViewport()
  233 |     const unreadQuestion = page
  234 |       .getByRole('region', { name: 'Problem discussion', exact: true })
  235 |       .filter({ hasText: `${text} EN` })
  236 |     await expect(
  237 |       unreadQuestion.getByRole('button', { name: /There is an unread reply/ }),
  238 |     ).toBeVisible()
  239 |     await expect(unreadQuestion.locator('.bg-status-danger')).toHaveCSS('animation-name', 'none')
  240 |     await unreadQuestion
  241 |       .getByRole('button', { name: /There is an unread reply/ })
  242 |       .screenshot({ path: testInfo.outputPath('question-unread-en-indicator.png') })
  243 |     await unreadQuestion
  244 |       .locator('..')
  245 |       .screenshot({ path: testInfo.outputPath('question-unread-dark-en-reduced-320.png') })
  246 |     await expect(page.getByRole('button', { name: /New replies \(/ })).toHaveCount(0, {
  247 |       timeout: 15_000,
  248 |     })
  249 |   } finally {
  250 |     expect(
  251 |       (
  252 |         await page.request.put('/student/api/v1/auth/locale', {
  253 |           headers: localeHeaders,
  254 |           data: { locale: 'ru' },
  255 |         })
  256 |       ).status(),
  257 |     ).toBe(200)
  258 |   }
  259 |   await staff.close()
  260 | })
  261 | 
```