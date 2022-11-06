"use strict";

const CELL_SIZE_IN_REM = 3;
const MODAL_WIDTH_IN_CELLS = 5;
const MODAL_HEIGHT_IN_CELLS = 3;
const FOG_OF_WAR = 15;
const FOR_OPACITY_LEN = 12;

const DEBUG = false;

const mapAsString = `
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\to\to\to\t1\t1\t2\t6\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\tx\t1\t1\t4\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t5\t3\tx\t3\t5\t10\tx
x\to\to\to\t1\t1\t2\tx\tx\tx\tx\tx\tx\tx\t4\tx\t4\t4\tx\t1\t3\t3\t1\tx\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t4\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t3\tx\t1\t3\t5\tx
x\to\to\to\t1\t1\t2\tx\t1\t1\t1\tx\t4\tx\t8\tx\t1\t1\tx\t1\t1\t1\t1\t4\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t4\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t3\tx\t1\t1\t3\tx
x\t1\t1\t1\t1\t1\t2\t3\t1\t4\t1\t4\t1\tx\tx\tx\t1\t1\tx\tx\tx\tx\tx\tx\t3\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t3\tx\t1\t1\t1\tx
x\t2\t2\t2\t2\t2\t2\tx\t4\tx\t1\t1\t1\t1\t1\t1\t1\t1\t4\t1\t1\t1\t1\t1\t1\t1\tx\t2\t1\t2\t1\t2\t1\t2\t1\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\tx\t3\tx\t6\tx\tx\tx
x\t5\tx\tx\tx\t4\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\t1\t4\t1\t1\t1\t1\t1\t1\t1\tx\t1\t2\t1\t2\t1\t2\t1\t2\t5\t1\t1\t1\t1\t1\t1\tx\t2\t2\tx\t1\t2\t1\t2\t1\tx
x\t1\t1\t1\tx\t1\t1\t1\t2\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\t1\t2\t1\t2\t1\t2\t1\tx\t1\t1\t1\t1\t1\t1\tx\t2\t2\tx\t2\t1\t2\t1\t2\tx
x\t1\t3\t1\tx\t1\t1\t1\t2\t2\tx\t8\t6\t3\t1\t1\t1\t3\t1\t1\t1\t3\t1\t1\t1\t3\tx\t1\t2\t1\t2\t1\t2\t1\t2\tx\t1\t1\t1\t1\t1\t1\tx\t2\t2\tx\t1\t2\t1\t2\t1\tx
x\t1\t3\t1\tx\t1\t1\t1\t2\t2\tx\t6\t3\t1\t3\t1\t3\t1\t3\t1\t3\t1\t3\t1\t3\t1\t4\t2\t1\t2\t1\t2\t1\t2\t1\tx\t1\t1\t1\t1\t1\t1\tx\t2\t2\tx\t2\t1\t2\t1\t2\tx
x\t1\t1\t1\tx\t1\t1\t1\t2\t2\tx\t3\t1\t1\t1\t3\t1\t1\t1\t3\t1\t1\t1\t3\t1\t1\t4\t1\t2\t1\t2\t1\t2\t1\t2\tx\t1\t1\t1\t1\t1\t1\tx\t2\t2\tx\tx\tx\tx\tx\tx\tx
x\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\t6\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\tx\tx\t6\tx\t4\t4\t4\tx\t9\tx
x\t1\t1\t1\tx\t1\tx\t2\t2\t2\t2\t2\t2\t2\tx\t3\t2\t3\tx\t1\t1\t1\t1\t5\t2\t5\t1\t1\t1\t1\tx\t3\t3\t3\t9\tx\t1\t1\t1\t1\t1\t1\t3\t3\t3\t3\t3\tx\t5\t5\t5\tx
x\t1\t3\t1\tx\t1\tx\t2\t2\t2\t2\t2\t2\t2\tx\t2\t3\t2\tx\t1\t3\t3\t1\tx\t2\tx\t1\t3\t3\t1\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\t1\t3\t1\tx\t1\tx\t6\t6\tx\tx\tx\tx\tx\tx\t3\t2\t3\tx\t1\t1\t1\t1\tx\t2\tx\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t6\t1\t1\tx\t1\t2\t1\t2\t1\t2\t1\t2\t1\tx
x\t1\t1\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\tx\t2\t4\t5\t1\t2\t4\t5\t1\t2\tx
x\t1\t3\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\t1\t1\t1\t1\t1\t1\t4\t2\t2\t4\t4\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\tx\t1\t5\t4\t2\t1\t5\t4\t2\t1\tx
x\t1\t3\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t2\t6\t1\t1\t1\t1\t1\t1\t4\t2\t2\t4\t8\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\tx\t2\t4\t5\t1\t2\t4\t5\t1\t2\tx
x\t1\t1\t1\t5\t1\t5\t1\t3\t1\t3\t1\t3\t1\t3\t1\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\tx\t1\t5\t4\t2\t1\t5\t4\t2\t1\tx
x\tx\tx\tx\tx\t6\tx\t1\t3\t1\t3\t1\t3\t1\t3\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t4\t1\t1\t1\t1\t1\t1\t1\tx\t2\t1\t2\t1\t2\t1\t2\t1\t2\tx
x\t1\t1\t1\tx\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t4\t4\tx
x\t1\t3\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx\t1\tx\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx
x\t1\t3\t1\t6\t2\t6\t2\t1\t2\t1\t2\t1\t2\t1\t2\t1\t2\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx
x\t1\t1\t1\t6\t2\t6\t1\t2\t1\t2\t1\t2\t1\t2\t1\t2\t1\tx\t1\tx\t2\tx\t3\t3\t3\t3\t3\t3\t6\t2\tx\t1\tx\t2\t2\tx\t2\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx
x\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t3\tx\tx\tx\tx\t3\tx\t2\tx\t1\tx\t2\tx\tx\t2\t2\t2\t2\t2\t2\tx\t2\tx\t2\t2\t2\tx\t2\tx
x\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\tx\t2\tx\t3\tx\t9\t10\tx\t3\tx\t2\tx\t1\tx\t2\t2\tx\t2\t2\t2\t2\t2\tx\tx\t2\tx\t2\t2\t2\tx\t2\tx
x\t1\t3\t1\tx\tx\tx\t4\tx\tx\tx\tx\tx\t1\t3\t1\t3\t1\tx\t1\tx\t2\tx\t3\t7\t8\t9\tx\t3\tx\t2\tx\t1\tx\t2\t2\tx\t2\t2\t2\t2\tx\tx\t2\t2\tx\tx\tx\tx\tx\t2\tx
x\t1\t3\t1\t5\t1\t1\t1\t1\t1\t1\t1\tx\t1\t3\t1\t3\t1\tx\t1\tx\t2\tx\t3\tx\tx\tx\tx\t3\tx\t2\tx\t1\tx\t2\t2\tx\t2\t2\t2\tx\tx\t2\t2\t2\t2\t2\t2\tx\tx\t2\tx
x\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\tx\t2\tx\t3\t3\t3\t3\t3\t3\tx\t2\tx\t1\tx\t2\t2\tx\t2\t2\t2\tx\t2\t2\t2\t2\t2\t2\tx\tx\t2\t2\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t2\t2\tx\t2\t2\t2\tx\t2\t2\t2\t2\t2\tx\tx\t2\t2\t2\tx
x\t1\t1\tx\t1\t1\t1\t4\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\tx\t1\t5\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx\t1\tx\t2\tx\tx\tx\t2\t2\tx\t2\t2\t2\t2\tx\tx\t2\t2\t2\t2\tx
x\t1\t1\tx\t1\t3\t1\tx\t1\t3\t1\tx\t1\t1\t1\t1\t1\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx
x\t1\t1\tx\t1\t3\t1\tx\t1\t3\t1\tx\t3\t3\t3\t3\t3\t3\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx
x\t1\t1\t3\t1\t1\t1\tx\t1\t1\t1\t5\t1\t1\t1\t1\t1\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\tx\t8\tx\t1\t1\tx\t1\t1\tx\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t2\t3\t4\t5\t5\t5\t4\t3\t2\t1\tx
x\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t3\t3\t3\t3\t3\t3\tx\t4\tx\t1\t1\tx\t1\t1\tx\t1\t1\tx\t1\t3\t1\tx\t1\t3\t3\t3\t1\tx\t1\t2\t3\t4\t4\t4\t4\t4\t3\t2\t1\tx
x\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t2\tx\t1\t1\tx\t1\t1\tx\t1\t1\tx\t1\t3\t1\tx\t1\t3\t9\t3\t1\tx\t1\t2\t3\t3\t3\t3\t3\t3\t3\t2\t1\tx
x\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t4\tx\tx\tx\tx\t1\t1\tx\t1\t1\tx\t1\t1\tx\t1\t1\t1\tx\t1\t3\t3\t3\t1\tx\t1\t2\t2\t2\t2\t2\t2\t2\t2\t2\t1\tx
x\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\tx\tx\t4\tx\tx\t4\tx\tx\t4\tx\t1\t3\t1\tx\t1\t1\t1\t1\t1\t6\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx
x\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\t5\t1\t1\t5\t2\t2\t2\t2\t2\tx\t1\t3\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t7\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t5\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx
x\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t6\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx\tx
x\t1\t3\t1\t3\t1\t3\t1\t3\t1\t3\t1\tx\tx\tx\tx\tx\tx\t1\t1\tx\t1\t3\t1\t3\t1\t3\t1\tx\t9\t3\t3\t3\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx\tx\tx
x\t1\t3\t1\t3\t1\t3\t1\t3\t1\t3\t1\t1\t1\t1\t3\t3\tx\t1\t1\tx\t1\t3\t1\t3\t1\t3\t1\tx\tx\tx\tx\t6\tx\t4\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\t1\t2\tx\tx\t8\tx
x\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t3\t3\tx\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t5\t1\t1\t1\tx\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t1\t2\tx\tx\t1\t1\tx
x\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t3\t1\tx\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t2\t7\tx\t1\t1\t1\tx
x\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t5\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t5\t1\t3\t1\tx\tx\tx\tx\tx\t4\tx\t1\t1\t1\t1\t2\t7\t7\to\t1\t1\t3\tx
x\t1\t1\t1\t1\t1\t1\tx\t1\t3\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t3\t3\t1\t3\t3\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t2\tx\tx\to\to\t1\t3\t5\tx
x\t3\t1\t1\t1\t1\t1\tx\t3\t5\t3\tx\t1\t1\t2\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\t3\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t2\tx\tx\t1\t1\t1\t3\t5\t6\tx
x\t5\t3\t1\t1\t1\t1\tx\t1\t3\t1\tx\t1\t2\t4\tx\t1\tx\t1\tx\t1\tx\t1\t3\t3\t1\t3\t3\t1\tx\t1\t3\t1\tx\t1\t1\t1\t1\t1\tx\t1\t2\tx\tx\t1\t1\t1\t3\t5\t6\t7\tx
x\t10\t5\t3\t1\t1\t1\t5\t1\t1\t1\tx\t2\t4\t8\tx\t1\t1\t1\tx\t1\t4\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t5\t1\t1\t1\t1\t1\t5\t2\tx\tx\t8\t1\t1\t3\t5\t6\t7\t10\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
`;

const chestsAsObj = [
  {
    x: 50, y: 1, amount: 10, bonus: 3,
    html: `Известный американский физик и математик, один из создателей векторного анализа Джозайя Гиббс (1839–1903), был очень неразговорчивым человеком и обычно молчал на заседаниях Ученого Совета Йельского университета, в котором преподавал. Но однажды он не сдержался. На одном из заседаний зашел спор о том, чему больше уделять внимания в новых программах — иностранным языкам или математике. Не выдержав, Гиббс поднялся с места и произнес целую речь: «Математика — это язык!»`,
  },
  {
    x: 14, y: 3, amount: 8, bonus: 2,
    html: `Когда Харди навещал в больнице Рамануджана, он, по его словам, начал разговор с того, что «пожаловался» на то, что приехал на такси со скучным, непримечательным номером «1729». Рамануджан разволновался и воскликнул: «Харди, ну как же, Харди, это же число — наименьшее натуральное число, представимое в виде суммы кубов двумя различными способами!». Вот эти способы: 1729 = 1³ + 12³ = 9³ + 10³`,
  },
  {
    x: 11, y: 8, amount: 8, bonus: 2,
    html: `С именем знаменитого Пьера Ферма связано много тайн. Однажды он получил письмо с вопросом: «Является ли простым число 100895598169?» Ферма незамедлительно ответил, что это двенадцатизначное число является произведением двух простых чисел: 898423 и 112303. Способ исследования числа он не раскрыл.<br><a href="http://kvant.mccme.ru/1972/07/tak_ili_ne_tak_dejstvoval_ferm.htm" target="_blank">Продолжение истории</a>.`,
  },
  {
    x: 50, y: 11, amount: 9, bonus: 2,
    html: `Что лучше: вечное блаженство или бутерброд с ветчиной? На первый взгляд кажется, что вечное блаженство лучше, но в действительности можно доказать, что это не так! Судите сами. Что лучше вечного блаженства? <i>Ничего</i>. А бутербод с ветчиной лучше, чем <i>ничего</i>. Следовательно, бутерброд с ветчиной лучше, чем вечное блаженство.`,
  },
  {
    x: 34, y: 12, amount: 9, bonus: 2,
    html: `Когда математик Джордж Данциг был еще студентом, он часто засиживался за занятиями до поздней ночи. Однажды он из-за этого проспал и опоздал на полчаса на лекцию профессора Неймана. Усевшись за парту Джордж быстро переписал две задачи с доски, решив, что это домашнее задание. Задачи были очень сложны, но к следующему занятию он всё-таки их сделал. Когда он принёс решения профессору, Нейман молча взял листки с решениями и убрал в портфель, так что Джордж решил, что профессор всё ещё сердится на него за то опоздание. А через несколько недель профессор Нейман с криком ворвался в дом Джорджа в шесть утра! Оказалось, что студент Джордж Данциг нашёл правильное решение двух задач из области математический статистики, которые до тех пор считались неразрешимыми. Сам Джордж об этом и не подозревал, так как на занятие опоздал и не слышал, что говорил профессор Нейман о задачах на доске. Он попросту не знал о репутации этих двух задач!`,
  },
  {
    x: 29, y: 17, amount: 8, bonus: 2,
    html: `Любые две грани тетраэдра имеют общее ребро, а любые две вершины соединены общим ребром.
А может ли быть какой-то другой многогранник у которого любые две грани имеют общее ребро?
Пока удалось построить только один такой многогранник: в 1977 году Лайош Силлаши построил полиэдральный тор (многогранник Силлаши).
<br>
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/7/72/Szilassi_polyhedron.gif/220px-Szilassi_polyhedron.gif">
<br>
У нас в 179-й школе есть крупная модель этого многогранника. Может быть, вам удастся уговорить кого-нибудь из старших преподавателей вам её показать?`,
  },
  {
    x: 25, y: 25, amount: 9, bonus: 2,
    html: `В 1852 году английский ботаник и логик Фрэнсис Гутри работал в типографии. При составлении карты графств Англии, он обратил внимание, что для такой цели хватает четырёх красок.
Гутри рассказал об этом своему брату, а тот — известному математику Августу де Моргану.
Де Морган заинтересовался вопросом: можно ли любую карту покрасить в 4 цвета?
От него этот забавный вопрос стал известен математикам Англии, и довольно неожиданно оказалось, что, несмотря на внешнюю простоту, доказать утверждение никак не получается.
В 1878 году Артур Кэли официально сформулировал «Проблему четырёх красок».
За решение проблемы брались самые авторитетные математики не только Англии, но и мира.
Несколько раз задача объявлялась решённой, но затем в решений находили ошибку. Ошибки исправлялись, но годы спустя обнаруживались новые — в исправленных решениях.
Теорема о четырёх красках была доказана только через 100 лет, в 1976 году — и стала первой математической теоремой, доказанной с помощью компьютерных вычислений.`,
  },
  {
    x: 26, y: 25, amount: 10, bonus: 9,
    html: `Гугол — это число вида 100...00 со 100 нулями.
В 1938 году известный американский математик Эдвард Казнер гулял по парку с двумя своими племянниками и обсуждал с ними большие числа. В ходе разговора зашла речь о числе со ста нулями, у которого не было собственного названия. Один из племянников, девятилетний Милтон Сиротта, предложил назвать это число «гугол» (англ. googol). 
Термин «гугол» не имеет серьёзного теоретического и практического значения. Казнер предложил его для того, чтобы проиллюстрировать разницу между невообразимо большим числом и бесконечностью: гугол больше, чем количество атомов в известной нам части Вселенной, которых, по разным оценкам, насчитывается от 10⁷⁹ до 10⁸¹.
Название компании Google является искажённым написанием слова «googol». Создатели известной поисковой машины хотели использовать термин «googol» в качестве названия, но при регистрации выяснилось, что такой домен уже занят.`,
  },
  {
    x: 25, y: 26, amount: 8, bonus: 2,
    html: `Пожалуй, один из лучших ответов на вопрос «Кому нужна математика?» дал математик по имени Мартин Гротшел.
Как-то раз немецкое правительство решило выделить целевым образом значительные суммы на развитие самых
передовых и необходимых областей науки. На заседание государственной комиссии были приглашены представители всех наук. Гротшел представлял математику и выступал последним. Заседание уже подходило к концу, чиновники сидели осоловевшие от обрушенного на них потока информации и энтузиазма ораторов. Гротшел вышел на трибуну и сказал примерно следующее:
<br>
— Уважаемые господа! Я не буду утомлять вас длинной речью, а просто приведу пример. Недавно мы получили заказ от большой страховой компании, планирующей создать автосервис для своих клиентов. Идея очень проста: если у клиента в дороге сломалась машина, он может позвонить по телефону и к нему тут же приедет аварийная служба. Вопрос в том, как правильно организовать такой сервис. В принципе, задачу можно решить довольно просто — например, приставить к каждому клиенту личную аварийную машину с механиком. Тогда клиент в любой момент немедленно получит помощь. Но это очень дорого! Другой вариант — вообще не связываться с аварийным сервисом. Клиенты могут ждать до бесконечности, зато это не будет стоить им ни цента. Так вот. Если вас эти решения не устраивают, то я должен вам сообщить, что для любых других вариантов понадобится математика! Спасибо за внимание.`,
  },
  {
    x: 26, y: 26, amount: 9, bonus: 2,
    html: `Легковой автомобиль — довольно сложная штука. И вот оказывается, сделать так, чтобы он мог поворачивать без проскальзывания колёс, не получится без геометрии! При повороте передние колёса не параллельны друг другу и поворачиваются каждое на свой угол. Механическую конструкцию, которая обеспечивает поворот колёс на нужный угол, придумал француз, каретных дел мастер Шарль Жанто (Charles Jeantand). Однако для карет, передвигавшихся с малыми скоростями, это было не так существенно, как для машин, и изобретение Жанто было забыто. Лишь почти через три четверти века два отца автомобилестроения, два немца, два инженера — Готтлиб Даймлер (Gottlieb Wilhelm Daimler) и Карл Бенц (Karl Friedrich Michael Benz) — изобретая свои автомобили, возвращаются к трапеции Жанто. В 1889 году Даймлер получает патент на «способ независимого управления передними колёсами с разновеликими радиусами поворота».
<br>
На сайте <a href="https://etudes.ru/etudes/steering-geometry/" target="_blank">математических этюдов</a> есть подробности про эту конструкцию.`,
  },
  {
    x: 19, y: 34, amount: 8, bonus: 2,
    html: `Имя Николая Ивановича Лобачевского не гремело в мировом научном сообществе, пока он был жив. Современник Пушкина и Пирогова, он не получал премий, о нем не писали на первых полосах газет, хотя как ректор одного из ведущих российских университетов он был известен — как в Казани, так и за ее пределами. Первые публикации Лобачевского по неевклидовой геометрии вышли в 1829–1830 гг. в журнале «Казанский вестник»
Что же такое неевклидова геометрия? Это — геометрическая теория, основанная на тех же основных аксиомах, что и обычная евклидова геометрия, за исключением аксиомы о параллельных прямых.
В аксиоме «На плоскости через точку, не лежащую на данной прямой, можно провести ровно одну прямую, параллельную данной» концовка заменена на «можно провести по крайней мере две прямые, не пересекающие данную».
Оказывается, геометрия Лобачевского связана со специальной теорией относительности, без хорошего понимания которой невозможно сделать GPS.`,
  },
  {
    x: 36, y: 36, amount: 9, bonus: 2,
    html: `Неваляшка возвращается в своё исходное положение благодаря грузу внизу игрушки. А в 2006-м году венгерские математики Домокош и Варконьи придумали пример выпуклого тела (без полостей и «грузов»), обладающее этим свойством. Они назвали его гё́мбёц. На это у них ушло 10 лет.<br><a href="https://www.youtube.com/watch?v=J-5TIS49Kt8&t=1s" target="_blank">О гёмбёце рассказывает математик Николай Андреев</a>`,
  },
  {
    x: 29, y: 42, amount: 9, bonus: 2,
    html: `Паркетом называют разбиение плоскости на многоугольники так, что любые две фигуры пересекаются либо по целой стороне, либо по вершине, либо не пересекаются вообще. Разумеется, придумать таких разбиений можно очень много, но математиков интересуют только достаточно симметричные паркеты. Легко придумать паркет из треугольников (любых) или прямоугольников. Однако наиболее сложный случай паркета на плоскости — это пятиугольный паркет. В 1918 году Карл Райнхардт описал пять классов таких паркетов. Долгое время этот список считался полным, пока в 1968 году Роберт Кершнер вдруг не обнаружил еще три таких класса. В 1975 году математик Ричард Джеймс увеличил это число до девяти. Тут в истории начинается самое интересное — об открытии Джеймса написал журнал Scientific American.
Статью увидела Мардж Райс, американская домохозяйка и по совместительству математик-любитель. Разработав собственную систему записи пятиугольных замощений она за 10 лет довела их количество до 14. И вот, наконец, спустя 30 лет ученые из Вашингтонского университета в Ботелле открыли 15-е замощение. Сделали они это с помощью компьютера. И вот наконец в июле 2017 года стало известно, что француз Михаэль Рао доказал, что ничего, кроме этих семейств, нет.
<br>
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/PentagonTilings15.svg/1920px-PentagonTilings15.svg.png" style="width:100%">
`,
  },
  {
    x: 50, y: 43, amount: 8, bonus: 2,
    html: `Формулу для площади круга можно запомнить при помощи пиццы. Пицца радиусом <i>ц</i> и толщиной <i>а</i> имеет объём <i>пи</i>∙<i>ц</i>∙<i>ц</i>∙<i>а</i> = 𝜋 ц²∙a`,
  },
  {
    x: 1, y: 50, amount: 10, bonus: 3,
    html: `Известный немецкий алгебраист Эрнст Эдуард Куммер (1810–1893) очень плохо умел считать в уме. Если при чтении лекции ему надо было выполнить простенький расчет, он обычно прибегал к помощи студентов.
Однажды ему надо было умножить 7 на 9. Он начал вслух рассуждать:
<br>
— Гм... это не может быть 61, потому что 61 — простое число. Это не может быть и 65, потому что 65 делится на 5. 67 — тоже простое число, а 69 — явно слишком много. Остается только 63...`,
  },
  {
    x: 14, y: 50, amount: 8, bonus: 2,
    html: `Рассказывают, что знаменитый французский математик и просветитель Жан Даламбер (1717–1783) каждый раз, когда излагал студентам собственную теорему, неизменно говорил: «А сейчас, господа, мы переходим к теореме, имя которой я имею честь носить!»`,
  },
  {
    x: 43, y: 50, amount: 8, bonus: 2,
    html: `Многие известные физики-теоретики отличались незаурядными математическими способностями. Одним из них был нобелевский лауреат Поль Дирак.
Дирак, будучи еще студентом, участвовал в математическом конкурсе, где в числе других была и такая задача.
<br>
Три рыбака наловили рыбы и легли спать. Первый из них проснулся утром и решил уехать домой. Своих товарищей он не стал будить, а разделил всю рыбу на три части. Но при этом одна рыба оказалась лишней. Недолго думая, он швырнул ее в воду, забрал свою часть и уехал домой. Потом проснулся второй рыбак. Он не знал, что первый рыбак уже уехал, и тоже поделил всю рыбу на три равные части, и, конечно, одна рыба оказалась лишней. Он тоже закинул он ее подальше от берега и со своей долей удалился. Последний рыбак тоже не заметил, что его товарищей уже нет. Разделил ее на три равные части, выбросил одну лишнюю рыбу в воду, забрал свою долю и был таков.
В задаче спрашивалось, какое наименьшее количество рыб могло быть у рыбаков.
<br>
Дирак предложил такое решение: рыб было (–2). После того как первый рыбак совершил поступок, швырнув одну рыбу в воду, их стало (–2) – 1 = –3. Потом он ушел, унося под мышкой (–1) рыбу. Рыб стало (–3) – (–1) = –2. Второй и третий рыбаки просто повторили поступок их товарища.`,
  },
  {
    x: 50, y: 50, amount: 10, bonus: 5,
    html: `Однажды к Эрнесту Резерфорду за помощью обратился его коллега из Копенгагена, который принимал экзамен по физике и собирался поставить студенту неуд, но студент был категорически не согласен и говорил, что заслуживает высший балл.
В билете просили объяснить, как с помощью барометра определить высоту здания. 
Ответ студента был таким: "Нужно подняться с барометром на крышу здания, привязать его к длинной веревке, спустить его по веревке вниз, потом втянуть его обратно и измерить длину веревки, которая покажет точную высоту здания".
Резерфорд отметил, что экзамен был по физике и следовало бы при ответе продемонстрировать знания по предмету.
В ответ студент предложил Резерфорду в общей сложности больше тридцати вариантов.
<br>
— Ладно, оценка "отлично". Но скажите, неужели вы в самом деле не знали традиционного ответа, которого от вас ждал преподаватель с разницой давлений?
<br>
— Знал, конечно. Но я за время обучения в школе и колледже по горло насытился тем, что учителя навязывают ученикам свой способ мышления и решения.
<br>
Студента этого звали Нильс Бор.`,
  },
];


const scene = {
  $game: undefined,
  $header: undefined,
  $gameTable: undefined,
  $modal: undefined,
  $popup: undefined,
  $popupText: undefined,
  $popupButton1: undefined,
  $popupButton2: undefined,
  map: undefined,
  width: undefined,
  height: undefined,
  chests: {},
  opened: [],
  scores: {},
  flags: {},
  myFlag: undefined,
};


function showPopupWide($cell, html, button1, buttonTitle1, buttonOnclick1) {
  const curRem = parseFloat(getComputedStyle(document.documentElement).fontSize);
  scene.$modal.style.top = `${window.scrollY + CELL_SIZE_IN_REM * curRem}px`;
  scene.$modal.style.left = `${scene.$gameTable.offsetLeft + window.scrollX}px`;
  scene.$modal.style.width = `${Math.min(window.innerWidth, 1000)}px`;
  scene.$modal.style.height = `calc(100% - ${CELL_SIZE_IN_REM}rem)`;
  // Полный треш здесь!
  scene.$modal.style.transform = 'none';
  scene.$modal.style.margin = 'auto';
  scene.$popupText.innerHTML = html;
  scene.$popupButton1.innerText = button1;
  scene.$popupButton1.title = buttonTitle1;
  scene.$popupButton1.onclick = buttonOnclick1;
  scene.$popupButton1.focus();
  scene.$popup.style.display = "block";
  scene.$popup.style.textAlign = "left";
  scene.$popupButton2.style.display = "none";
}


function showPopup($cell, html, button1, buttonTitle1, buttonOnclick1, button2 = undefined, buttonTitle2 = undefined, buttonOnclick2 = undefined) {
  const curRem = parseFloat(getComputedStyle(document.documentElement).fontSize);
  const x = $cell.offsetLeft + $cell.offsetWidth / 2 - document.body.scrollLeft;
  const y = $cell.offsetTop + $cell.offsetHeight / 2 - document.body.scrollTop;
  const halfModalWidth = CELL_SIZE_IN_REM * MODAL_WIDTH_IN_CELLS * curRem / 2;
  const halfModalHeight = CELL_SIZE_IN_REM * MODAL_HEIGHT_IN_CELLS * curRem / 2;
  let useTop = y - halfModalHeight - CELL_SIZE_IN_REM * curRem / 2;
  if (useTop < halfModalHeight) {
    useTop = y + halfModalHeight + CELL_SIZE_IN_REM * curRem / 2;
  }
  useTop += CELL_SIZE_IN_REM * curRem;

  // Полный треш здесь!
  scene.$modal.style.top = `${useTop}px`;
  scene.$modal.style.left = `${Math.min(Math.max(x, halfModalWidth), window.scrollX + window.innerWidth - halfModalWidth)}px`;
  scene.$modal.style.width = `${CELL_SIZE_IN_REM * MODAL_WIDTH_IN_CELLS}rem`;
  scene.$modal.style.height = `${CELL_SIZE_IN_REM * MODAL_HEIGHT_IN_CELLS}rem`;
  scene.$modal.style.transform = 'translate(-50%, -50%)';
  scene.$modal.style.margin = '0';
  scene.$popup.style.textAlign = "center";

  scene.$popupText.innerHTML = html;
  scene.$popupButton1.innerText = button1;
  scene.$popupButton1.title = buttonTitle1;
  scene.$popupButton1.onclick = buttonOnclick1;
  scene.$popupButton1.focus();
  if (button2 === undefined) {
    scene.$popupButton2.style.display = "none";
  } else {
    scene.$popupButton2.style.display = "inline-block";
    scene.$popupButton2.innerText = button2;
    scene.$popupButton2.onclick = buttonOnclick2;
    scene.$popupButton2.title = buttonTitle2;
  }
  scene.$popup.style.display = "block";
}

function hidePopup() {
  const popup = document.getElementById("popup");
  popup.style.display = "none";
}


function convertMap(mapAsString) {
  const map = mapAsString
    .trim()
    .split('\n')
    .map((row) => row.trim().split('\t').map((cell) => parseInt(cell) || cell));
  const width = map[0].length;
  const height = map.length;
  const chests = {};
  for (const chest of chestsAsObj) {
    const {x, y, amount, html, bonus} = chest;
    const cellId = y * width + x;
    chests[cellId] = {amount, html, bonus, isOpened: false};
  }
  return {map, width, height, chests};
}

async function postData(url = '', data = {}) {
  const response = await fetch(url, {
    method: 'POST', // *GET, POST, PUT, DELETE, etc.
    mode: 'cors', // no-cors, *cors, same-origin
    cache: 'no-cache', // *default, no-cache, reload, force-cache, only-if-cached
    credentials: 'same-origin', // include, *same-origin, omit
    headers: {'Content-Type': 'application/json'},
    redirect: 'follow', // manual, *follow, error
    referrerPolicy: 'no-referrer', // no-referrer, *no-referrer-when-downgrade, origin, origin-when-cross-origin, same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
    body: JSON.stringify(data), // body data type must match "Content-Type" header
  });
  return response.json(); // parses JSON response into native JavaScript objects
}


function succesBuy($cell) {
  $cell.className = 'so';
  scene.opened.push($cell.cellID);
  updateMap();
  renderHeader();
}

function postBuy($cell, amount) {
  postData('/game/buy', {x: $cell.coln, y: $cell.rown, amount})
    .then(resp => () => succesBuy($cell))
    .catch(err => {
      console.log(err);
      updateMap();
      renderHeader();
      $cell.style.border = '3px solid #f00';
    });
}

function postFlag($cell) {
  postData('/game/flag', {x: $cell.coln, y: $cell.rown})
    .then(resp => {
      // console.log(resp);
    });
}

function postOpenChest($cell) {
  postData('/game/chest', {x: $cell.coln, y: $cell.rown, bonus: $cell.chest.bonus})
    .then(resp => {
      // console.log(resp);
    })
    .catch(err => {
      console.log(err);
      updateMap();
      renderHeader();
      $cell.style.border = '3px solid #f00';
    });
}

function refreshData(response) {
  scene.opened.push(...response['opened'].map(([x, y]) => y * scene.width + x));
  scene.scores = {};
  for (const diff of response['events']) {
    if (diff > 0) {
      scene.scores[diff] = (scene.scores[diff] | 0) + 1;
    } else {
      buy(-diff);
    }
  }
  scene.flags = {};
  response['flags'].forEach(([x, y]) => {
    const cellId = y * scene.width + x;
    scene.flags[cellId] = (scene.flags[cellId] | 0) + 1;
  });
  response['chests'].forEach(([x, y]) => {
    if (x < 0 || y < 0) return;
    try {
      scene.$cells[y][x].chest.isOpened = true;
    } catch (e) {
      console.log(e);
    }
  });
  scene.myFlag = response['myFlag'] && response['myFlag'].length === 2 && response['myFlag'].y * scene.width + response['myFlag'].x;
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}


async function runTLAnimation(response) {
  // Парсим timestamp'ы
  response.forEach(obj => obj.tss = new Date(obj.ts).getTime());
  scene.$header.innerHTML = `<div></div>`;
  let timeOut = new URL(window.location).searchParams.get('ms');
  let realtime = false;
  let timePeriod;
  const destAnimationDurMs = (new URL(window.location).searchParams.get('dur'))*1000 || 20000;
  debugger;
  if (timeOut === undefined || timeOut === null) {
    timeOut = Math.max(4, 1000 / response.length);
  } else if (timeOut === '0') {
    realtime = true;
    timePeriod = response[response.length - 1].tss - response[0].tss;
  }
  let prevSleepStart = response[0].tss;
  for (let i = 0; i < response.length; i++) {
    let timeToSleep = 0;
    if (!realtime) {
      timeToSleep = +timeOut;
    } else {
      const delta = (response[i].tss - prevSleepStart) / timePeriod * destAnimationDurMs;
      if (delta > 4) {
        timeToSleep = delta;
        prevSleepStart = response[i].tss;
      }
    }
    const coln = response[i]['x'];
    const rown = response[i]['y'];
    const cellID = rown * scene.width + coln;
    scene.opened.push(cellID);
    if (timeToSleep >= 1) {
      await sleep(timeToSleep);
      updateMap();
      renderHeader();
    }
  }
  updateMap();
  renderHeader();
  scene.$header.innerHTML = `<div>Завершено</div>`;
}

function fetchInitialData() {
  scene.$header.innerHTML = `<div><p><span>...⚡</span> — загружаем информацию...</p></div>`;
  const tlCommandId = parseInt(new URL(window.location).searchParams.get('command_id'));

  if (! (tlCommandId > 0)) {
    postData('/game/me', {})
      .then(resp => {
        refreshData(resp);
        updateMap();
        renderHeader();
      });
  } else {
    postData(`/game/timeline/${tlCommandId}`, {})
      .then(resp => {
        runTLAnimation(resp);
      });
  }
}


function yesClicked($cell, amount) {
  $cell.textContent = "...";
  $cell.onclick = null;
  const successBuy = buy(amount);
  renderHeader();
  hidePopup();
  console.log(`Пытаемся открыть ячейку ${$cell.coln} ${$cell.rown} за ${amount}`);
  if (successBuy && !DEBUG) {
    postBuy($cell, amount);
  } else if (successBuy && DEBUG) {
    succesBuy($cell);
  }
}

function flagYesClicked($cell) {
  if (scene.myFlag) {
    scene.flags[scene.myFlag] = Math.max(0, (scene.flags[scene.myFlag] | 0) - 1);
  }
  scene.myFlag = $cell.cellID;
  scene.flags[scene.myFlag] = (scene.flags[scene.myFlag] | 0) + 1;
  updateMap();
  hidePopup();
  if (!DEBUG) {
    postFlag($cell);
  }
}

function noClicked($cell) {
  $cell.classList.remove('selected');
  hidePopup();
}

function okClicked($cell) {
  $cell.classList.remove('selected');
  hidePopup();
}


function onCellClick(ev) {
  const $cell = ev.target;

  // Определяем, есть ли рядом исследованные клетки
  const {rown, coln} = $cell;
  const upOpened = rown - 1 >= 0 && scene.$cells[rown - 1][coln].textContent === "o";
  const downOpened = rown + 1 < scene.height && scene.$cells[rown + 1][coln].textContent === "o";
  const leftOpened = coln - 1 >= 0 && scene.$cells[rown][coln - 1].textContent === "o";
  const rightOpened = coln + 1 < scene.width && scene.$cells[rown][coln + 1].textContent === "o";

  if (upOpened || downOpened || leftOpened || rightOpened) {
    $cell.classList.add('selected');
    // Проверяем, хватает ли денег купить
    const amount = +$cell.textContent;
    const whichToMinus = tryToBuy(amount);
    if (whichToMinus === undefined) {
      showPopup($cell, `Не хватает ⚡<br>Решите задачку!`, 'Буду решать!', 'Закрыть окно', () => okClicked($cell));
    } else {
      showPopup($cell, `Изучить клетку<br>за ${$cell.textContent}⚡?`, '✅ Да!', 'Да, изучить клетку!', () => yesClicked($cell, amount), '❌ Нет', 'Нет, вернуться назад', () => noClicked($cell));
    }
  } else {
    $cell.classList.add('selected');
    // showPopup(centerX, centerY, `Можно изучать<br>только соседние`, 'Ясно', 'Закрыть окно', () => okClicked($cell));
    showPopup($cell, `Поставить флаг <br>для всех в ячейку?`, '🚩 Да!', 'Да, поставить флаг!', () => flagYesClicked($cell), 'Нет', 'Нет, вернуться назад', () => noClicked($cell));
  }
}

function renderHeader() {
  scene.$header.innerHTML = Object.entries(scene.scores).map(([key, value]) => value > 0 ? `<div><p><span>${key}⚡</span> × ${value} </p></div>` : '').join('');
  if (scene.$header.innerHTML.length === 0) {
    scene.$header.innerHTML = `<div><p><span>0⚡</span> — чтобы получить энергию, нужно решить задачу </p></div>`;
  }
}

function tryToBuy(amount) {
  for (const [key, value] of Object.entries(scene.scores)) {
    if (value > 0 && key >= amount) {
      return key;
    }
  }
}


function showChestSecret(ev) {
  const $cell = ev.target;
  showPopupWide($cell, $cell.chest.html, 'Круто!', 'Закрыть окно', () => okClicked($cell));
}

function onClosedChestClick(ev) {
  const $cell = ev.target;
  $cell.chest.isOpened = true;
  $cell.className = 'openedChest';
  $cell.onclick = $cell.ondblclick = showChestSecret;
  scene.scores[$cell.chest.bonus] = (scene.scores[$cell.chest.bonus] | 0) + 1;
  postOpenChest($cell);
  showChestSecret(ev);
}


function buy(amount) {
  for (const [whichToMinus, value] of Object.entries(scene.scores)) {
    if (value > 0 && whichToMinus >= amount) {
      scene.scores[whichToMinus] -= 1;
      const diff = whichToMinus - amount;
      if (diff > 0) {
        scene.scores[diff] = (scene.scores[diff] | 0) + 1; // Хак на случай отсутствия ключа
      }
      return true;
    }
  }
  return false;
}

function updateMap() {
  // Сначала отмечаем открытые ячейки
  for (const cellID of scene.opened) {
    const rown = Math.trunc(cellID / scene.width);
    const coln = cellID % scene.width;
    if (scene.map[rown][coln] !== "x") {
      scene.map[rown][coln] = "o";
    }
  }
  // Теперь нужно сделать обход в ширину для того, чтобы добавить «туман войны»
  const distances = new Map();
  let curLayer = new Set();
  for (let rown = 0; rown < scene.map.length; rown += 1) {
    for (let coln = 0; coln < scene.map[0].length; coln += 1) {
      if (scene.map[rown][coln] === "o") {
        const cellID = rown * scene.width + coln;
        distances.set(cellID, 0);
        curLayer.add(cellID);
      }
    }
  }
  let steps = 0;
  while (curLayer.size > 0 && steps < FOG_OF_WAR) {
    let nextLayer = new Set();
    for (const cellID of curLayer) {
      const rown = Math.trunc(cellID / scene.width);
      const coln = cellID % scene.width;
      if (scene.map[rown][coln] === "x") {
        continue;
      }
      if (rown === 0 || coln === 0 || coln === scene.width - 1 || rown === scene.height - 1) {
        continue;
      } // Рамку не трогаем
      for (const diff of [-1, 1, -scene.width - 1, -scene.width, -scene.width + 1, +scene.width - 1, +scene.width, +scene.width + 1]) {
        const newcellID = cellID + diff;
        if (distances.get(newcellID) === undefined) {
          distances.set(newcellID, distances.get(cellID) + 1);
          nextLayer.add(newcellID);
        }
      }
    }
    curLayer = nextLayer;
    steps += 1;
  }


  // Теперь обновляем стили
  for (let rown = 0; rown < scene.map.length; rown += 1) {
    const valuesRow = scene.map[rown];
    for (let coln = 0; coln < valuesRow.length; coln += 1) {
      const cellValue = valuesRow[coln];
      const $cell = scene.$cells[rown][coln];
      const dist = distances.get($cell.cellID);
      const isBorder = rown === 0 || coln === 0 || coln === scene.width - 1 || rown === scene.height - 1;
      if (dist < FOG_OF_WAR || isBorder) {
        $cell.textContent = cellValue;
        $cell.className = `s${cellValue}`;
        if (+cellValue) {
          $cell.onclick = $cell.ondblclick = onCellClick;
        } else {
          $cell.onclick = $cell.ondblclick = null;
        }
        if (!isBorder && FOG_OF_WAR - dist <= FOR_OPACITY_LEN) {
          $cell.style.opacity = (FOG_OF_WAR - dist) / FOR_OPACITY_LEN;
        } else {
          $cell.style.opacity = 1;
        }
        // Обрабатываем сундуки
        if ($cell.chest) {
          if ($cell.chest.isOpened) {
            $cell.classList.add('openedChest');
            $cell.onclick = $cell.ondblclick = showChestSecret;
          } else {
            $cell.classList.add('closedChest');
            if (!+cellValue) {
              $cell.onclick = $cell.ondblclick = onClosedChestClick;
            }
          }
          $cell.style.opacity = 1;
        }
      } else {
        $cell.textContent = '';
        $cell.className = 'fog';
        $cell.onclick = $cell.ondblclick = null;
      }
      // Добавляем в ячейку флаги
      const addFlagsHtmls = [];
      for (let flRep = 0; flRep < (scene.flags[$cell.cellID] | 0); flRep++) {
        const rx = ((flRep * 0.71) % 1.5).toFixed(2);
        const ry = (-0.6 - (flRep * 0.61) % 1.8).toFixed(2); // от -2.4 до -0.6
        addFlagsHtmls.push(`<div class="flag" style="top: ${ry}rem; left: ${rx}rem; "></div>`);
      }
      $cell.innerHTML = $cell.textContent + addFlagsHtmls.join('');
    }
  }
  // Заголовок
  renderHeader();
}


function initialMapRender() {
  scene.$cells = [];
  for (let rown = 0; rown < scene.map.length; rown += 1) {
    const valuesRow = scene.map[rown];
    const $tableRow = scene.$gameTable.insertRow();
    const $cellsRow = [];
    scene.$cells.push($cellsRow);
    for (let coln = 0; coln < valuesRow.length; coln += 1) {
      const cellValue = valuesRow[coln];
      if (DEBUG && cellValue >= 8) {
        console.log({x: coln, y: rown, amount: cellValue, html: "", bonus: 2});
      }
      const $cell = $tableRow.insertCell();
      $cellsRow.push($cell);
      $cell.coln = coln;
      $cell.rown = rown;
      $cell.cellID = rown * scene.width + coln;
      $cell.chest = scene.chests[$cell.cellID];
      $cell.id = `${coln}_${rown}`;
    }
  }
}

function prepareWebsockets() {
  scene.curWebSocket = null;
  scene.wsConnectInterval = null;

  function onWebSocketOpen(ev) {
    // console.log('Websocket open', ev);
  }

  function onWebSocketMessage(ev) {
    // console.log('Message', ev);
    const resp = JSON.parse(ev.data);
    refreshData(resp);
    updateMap();
    renderHeader();
  }

  function onWebSocketClose(ev) {
    if (ev.wasClean) {
      // console.log('Clean connection end')
    } else {
      // console.log('Connection broken')
    }
    scene.curWebSocket = null;
    scene.wsConnectInterval = setInterval(() => {
      scene.curWebSocket = createWebSocketConnection();
    }, 2000);
  }

  function createWebSocketConnection() {
    let ws;
    if (window.location.host.startsWith('127.0.0.1')) {
      ws = new WebSocket('ws://' + window.location.host + '/game/ws');
    } else {
      ws = new WebSocket('wss://' + window.location.host + '/game/ws');
    }
    ws.onopen = onWebSocketOpen;
    ws.onmessage = onWebSocketMessage;
    ws.onclose = onWebSocketClose;
    if (scene.wsConnectInterval) {
      clearInterval(scene.wsConnectInterval);
      scene.wsConnectInterval = null;
    }
    return ws;
  }

  scene.wsConnectInterval = setInterval(() => {
    scene.curWebSocket = createWebSocketConnection();
  }, 2000);
  scene.curWebSocket = createWebSocketConnection();
}

function onScroll(ev) {
  localStorage.setItem('x', document.body.scrollLeft);
  localStorage.setItem('y', document.body.scrollTop);
}

function resumeScrol() {
  document.body.scrollLeft = +localStorage.getItem('x');
  document.body.scrollTop = +localStorage.getItem('y');
}

function init() {
  scene.$game = document.getElementById('game');
  scene.$header = document.getElementById('header');
  scene.$gameTable = document.getElementById('gameTable');
  scene.$modal = document.getElementById("modal-content");
  scene.$popup = document.getElementById("popup");
  scene.$popupText = document.getElementById("popupText");
  scene.$popupButton1 = document.getElementById("popupButton1");
  scene.$popupButton2 = document.getElementById("popupButton2");
  scene.$header = document.getElementById("header");
  Object.assign(scene, convertMap(mapAsString));

  initialMapRender();
  resumeScrol();
  document.body.addEventListener("scroll", onScroll);


  updateMap();
  if (!DEBUG) {
    fetchInitialData();
  } else {
    const response = {
      opened: [],
      events: [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
      flags: [],
      myFlag: null,
      chests: [],
    };
    refreshData(response);
    updateMap();
    renderHeader();
  }
  prepareWebsockets();
  setInterval(() => fetchInitialData(), 60 * 1000);
}


function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    document.documentElement.requestFullscreen();
  }
}

window.addEventListener('load', init);

