test_students = [
    {"chat_id": None, "type": 1, "level": "н", "name": "Григорий", "surname": "Ющенко", "middlename": "", "token": "token1", "online": 1, "grade": None, "birthday": None},
    {"chat_id": 1230, "type": 1, "level": "п", "name": "София", "surname": "Полякова", "middlename": "Алексеевна", "token": "token2", "online": 2, "grade": None, "birthday": None},
    {"chat_id": 1234, "type": 1, "level": "п", "name": "София", "surname": "Полякова", "middlename": "Борисовна",
     "token": "token7", "online": 2, "grade": None, "birthday": None},

    {"chat_id": 1231, "type": 1, "level": "п", "name": "Антон", "surname": "Михеенко", "middlename": "Михайлович", "token": "token3", "online": 1, "grade": None, "birthday": "2011-11-22"},
    {"chat_id": None, "type": 1, "level": "п", "name": "Антон", "surname": "Михеенко", "middlename": "Михайлович",
     "token": "token8", "online": 1, "grade": None, "birthday": "2022-11-22"},

    {"chat_id": None, "type": 1, "level": "н", "name": "Михаил", "surname": "Наумов", "middlename": "", "token": "token4", "online": 2, "grade": None, "birthday": None},
    {"chat_id": 1232, "type": 1, "level": "н", "name": "Амир М.", "surname": "Файзуллин", "middlename": "", "token": "token5", "online": 1, "grade": None, "birthday": None},
    {"chat_id": 1233, "type": 1, "level": "н", "name": "Марк", "surname": "Шерман", "middlename": "", "token": "token6", "online": 1, "grade": None, "birthday": None},
]
test_teachers = [
    {"chat_id": None, "type": 2, "level": None, "name": "Анна", "surname": "Гришина", "middlename": "10A", "token": "token101", "online": 1, "grade": None, "birthday": None},
    {"chat_id": 2120, "type": 2, "level": None, "name": "Надежда", "surname": "Ибрагимова", "middlename": "10Б", "token": "token102", "online": 2, "grade": None, "birthday": None},
]
test_problems = [
    {"id": 162, "level": "н", "lesson": 4, "prob": 4, "item": "", "title": "Две колонны из пяти бегунов", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Сколько раз было произнесено \"Привет\"", "cor_ans": "50", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 167, "level": "н", "lesson": 4, "prob": 9, "item": "", "title": "Стрелки на кремлёвских курантах", "prob_text": "", "prob_type": 4, "ans_type": "", "ans_validation": "", "validation_error": "", "cor_ans": "", "cor_ans_checker": "", "wrong_ans": "", "congrat": "", },
    {"id": 171, "level": "н", "lesson": 4, "prob": 11, "item": "", "title": "Периметр многоугольника", "prob_text": "", "prob_type": 4, "ans_type": "", "ans_validation": "", "validation_error": "", "cor_ans": "", "cor_ans_checker": "", "wrong_ans": "", "congrat": "", },
    {"id": 177, "level": "п", "lesson": 4, "prob": 4, "item": "", "title": "Колонны из 5 и 7 бегунов", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Сколько раз было произнесено \"Привет\"", "cor_ans": "70", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 182, "level": "п", "lesson": 4, "prob": 9, "item": "", "title": "Кремлёвские куранты", "prob_text": "", "prob_type": 4, "ans_type": "", "ans_validation": "", "validation_error": "", "cor_ans": "", "cor_ans_checker": "", "wrong_ans": "", "congrat": "", },
    {"id": 184, "level": "п", "lesson": 4, "prob": 11, "item": "", "title": "Гингема, Бастинда и 55 камушков", "prob_text": "", "prob_type": 4, "ans_type": "", "ans_validation": "", "validation_error": "", "cor_ans": "", "cor_ans_checker": "", "wrong_ans": "", "congrat": "", },
    {"id": 192, "level": "э", "lesson": 4, "prob": 4, "item": "а", "title": "Количество 4-значных чисел", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Введите ответ — сколько чисел", "cor_ans": "9000", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 193, "level": "э", "lesson": 4, "prob": 4, "item": "б", "title": "4-значные числа, 2-я цифра меньше 3-й", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Введите ответ — сколько чисел", "cor_ans": "4050", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 194, "level": "э", "lesson": 4, "prob": 4, "item": "в", "title": "4-значные числа, 1-я цифра меньше 3-й", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Введите ответ — сколько чисел", "cor_ans": "3600", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 195, "level": "э", "lesson": 4, "prob": 4, "item": "г", "title": "10-значные числа, цифры идут по убыванию", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Введите ответ — сколько чисел", "cor_ans": "1", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 196, "level": "э", "lesson": 4, "prob": 4, "item": "д", "title": "10-значные числа, цифры идут по возрастанию", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Введите ответ — сколько чисел", "cor_ans": "0", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 197, "level": "э", "lesson": 4, "prob": 4, "item": "е", "title": "6-значные числа, цифры идут по возрастанию", "prob_text": "", "prob_type": 1, "ans_type": 2, "ans_validation": "", "validation_error": "Введите ответ — сколько чисел", "cor_ans": "84", "cor_ans_checker": "", "wrong_ans": "Нет, не столько", "congrat": "Да, всё верно!", },
    {"id": 202, "level": "э", "lesson": 4, "prob": 9, "item": "", "title": "Букашки в 5-угольнике", "prob_text": "", "prob_type": 4, "ans_type": "", "ans_validation": "", "validation_error": "", "cor_ans": "", "cor_ans_checker": "", "wrong_ans": "", "congrat": "", },
    {"id": 204, "level": "э", "lesson": 4, "prob": 11, "item": "", "title": "Вилларибо и Виллабаджо", "prob_text": "", "prob_type": 4, "ans_type": "", "ans_validation": "", "validation_error": "", "cor_ans": "", "cor_ans_checker": "", "wrong_ans": "", "congrat": "", },
]
