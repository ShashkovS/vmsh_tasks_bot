"use strict";

const CELL_SIZE_IN_REM = 3;
const MODAL_WIDTH_IN_CELLS = 5;
const MODAL_HEIGHT_IN_CELLS = 3;
const FOG_OF_WAR = 8;
const FOR_OPACITY_LEN = 8;

const DEBUG = false;

const GAME_NUM = 6;

const mapAsString = `
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\to\to\t1\t1\t1\t1\t1\tx\t1\t2\t3\t1\t2\tx\t1\tx\t1\t1\t1\t1\t1\t1\t8\tx\t3\tx\t1\t1\t1\tx\t2\tx\t1\t1\t1\tx\t1\t7\t1\t1\t1\tx\t8\t1\t1\t2\t1\tx\t1\tx\t8\t1\t1\t1\t1\t2\t2\t1\t2\t1\t1\t1\t1\t2\t3\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t5\t2\t1\t2\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t3\tx\t8\tx
x\to\to\t1\tx\tx\tx\t1\tx\t2\t1\t1\t1\t1\tx\t7\tx\t2\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\t7\t1\t1\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx
x\t1\t1\t1\tx\t8\tx\t1\t2\t1\t1\t1\t1\t1\t5\t3\t1\t3\tx\t1\tx\t1\t1\t1\t2\t1\t1\t3\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx\t7\t1\t5\t1\t1\tx\t2\t1\t1\tx\t1\tx\t7\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t8\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\t3\t1\t3\tx\t1\tx\t2\t1\t3\tx
x\t1\tx\tx\tx\t2\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t2\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx
x\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t2\t1\t1\t1\t1\t1\t1\t1\t2\t1\t1\tx\t1\t1\t1\t1\t1\t5\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t5\tx\t1\t2\t2\t1\t1\tx\t1\tx\t1\t2\t1\t1\t1\t1\t1\tx\t1\tx\t3\tx\t2\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t2\t1\t1\t1\t7\t1\t1\t2\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx
x\t1\t1\t3\t7\t1\tx\tx\tx\tx\tx\t1\tx\tx\t1\t1\t1\t1\tx\t1\tx\t1\tx\tx\tx\t5\t5\t5\t5\tx\tx\tx\tx\t1\tx\tx\tx\t1\t1\t1\t1\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t3\tx
x\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t7\tx\t1\tx\t1\t1\t2\t1\t1\t1\t1\t3\t1\t1\t2\tx\t1\t3\t2\t1\t7\t2\t3\t1\t1\t1\t1\t1\t2\t3\t4\tx\t1\tx\t1\tx\t1\t1\t1\t1\t5\t1\t7\t1\t1\tx\t1\tx\t1\t1\t2\t1\t1\t1\t1\tx\t1\tx\t2\t1\t3\t1\t3\t1\t1\tx\t1\t1\t1\t2\t1\t1\t1\t2\t6\tx\t2\t1\t2\t1\t1\tx\t1\tx
x\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\t1\t1\t7\t1\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\tx\tx\tx\tx\tx\t2\t1\t1\t1\t1\t1\t1\tx\tx\t1\tx\t3\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx
x\t5\tx\t5\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t5\t1\t1\t6\t1\tx\t1\t6\t1\t1\t2\tx\t1\t1\t1\t4\t7\t1\t3\t1\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\t1\t5\t1\tx\t1\tx\t8\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx\t1\t3\t3\tx\t1\t3\t1\tx\t1\t1\t1\tx\t8\tx\t4\t3\t7\tx\t1\t2\t1\t1\t1\tx\t1\t1\t1\tx
x\t1\tx\tx\tx\t5\tx\t1\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\t1\t1\t1\t1\tx\tx\t1\t1\t1\tx\tx\tx\tx\tx\t2\t2\t1\t1\t1\t1\t3\t1\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\t4\t1\t1\t1\t1\tx\tx\tx\tx\t1\tx
x\t1\t1\t1\t2\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t2\t3\t1\t1\t1\t1\t1\t2\t1\t5\t1\t1\t1\tx\t1\tx\t1\t1\t1\t2\t1\tx\t1\t1\t1\tx\t1\tx\t7\t2\t3\tx\t3\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\tx\t2\t2\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t6\tx\t1\t7\t1\t5\t1\t1\t1\t2\t1\t1\t2\tx\t4\t1\t1\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\t1\t1\tx\t1\t1\t1\t1\tx\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t3\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\t1\t1\t1\t1\t1\tx\tx\tx\tx\t1\tx
x\t1\t1\t1\tx\t8\t1\t2\tx\t1\t1\t1\t1\t1\t6\t1\t1\t1\tx\t1\t6\t1\t1\t1\t1\t1\tx\t5\tx\t1\tx\t1\tx\t1\t1\t1\t1\t2\tx\t1\tx\t1\t1\t1\t2\t1\t3\t1\tx\t1\t1\t1\t1\t1\tx\t1\tx\t2\tx\t1\t1\t1\t3\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t3\tx\t8\t1\t1\tx\t1\tx\t1\t1\t1\tx\t6\tx\t1\tx\t1\t1\t1\t1\t1\t1\t2\t1\t1\t1\t2\tx
x\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t3\tx\tx\tx\t1\t2\t1\tx\t4\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\t1\t1\tx
x\t1\t7\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t3\t1\tx\t1\tx\t3\tx\t1\t4\t2\t1\t1\tx\t8\tx\t2\t2\t1\t1\t1\t1\t1\tx\t1\tx\t1\tx\t1\t1\t8\tx\t1\t1\t1\t3\t1\t3\t1\tx\t1\t1\t1\tx\t1\tx\t4\t3\t4\tx\t8\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t3\tx\t1\t1\t2\tx\t1\t2\t1\tx\t1\t1\t2\t1\t1\t1\t1\tx\t1\t4\t1\tx
x\t1\tx\tx\tx\t3\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\t2\t1\t1\t4\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\t1\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t3\t1\t1\tx
x\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t2\t1\t1\t1\t3\tx\t2\tx\t7\tx\t6\t1\t1\t1\t1\tx\t1\t1\t1\t2\t1\t1\t3\t5\t2\tx\t1\t2\t3\t3\t1\t1\t1\t1\t1\t1\t1\t3\t3\t1\t1\t2\t1\tx\t1\tx\t1\t1\t4\t3\t1\tx\t3\t2\t1\t1\t3\t1\t1\t5\t1\t7\t1\t3\t3\t1\t1\tx\t1\t1\t3\tx\t1\tx\t1\t1\t1\tx\t5\t1\t2\tx\t1\t1\t1\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\t2\tx\tx\tx\t2\tx\tx\t1\t2\t1\t1\tx\t5\tx\t3\tx\t1\tx\tx\tx\t7\tx\t1\tx\t1\tx\t6\tx\t1\tx\tx\tx\t1\t2\t1\t1\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\t5\tx\t1\tx\t1\tx\t1\t1\t2\tx
x\t7\t5\t1\tx\t8\tx\t2\t2\t2\tx\t1\t2\t5\t7\t1\tx\t1\t2\t3\tx\t1\t1\t1\t1\t3\t5\t1\t1\t1\tx\t3\tx\t1\t3\t1\t1\t2\tx\t1\tx\t1\tx\t3\tx\t5\tx\t1\t1\t2\tx\t2\t1\t1\t2\t1\t1\t5\t2\t1\tx\t1\t1\t3\t1\t1\tx\t1\t1\t1\tx\t1\tx\t3\t2\t1\tx\t2\t1\t1\tx\t1\t1\t1\tx\t3\t1\t2\tx\t1\t3\t1\tx\t1\tx\t1\t7\t1\t1\t1\tx
x\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\t3\t1\t1\t5\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\t2\t1\t1\t1\tx\t1\tx\tx\tx\t4\tx\tx\tx\t1\tx\t2\tx\t2\tx\t1\tx\t1\tx\t7\tx\tx\tx\t3\tx\tx\tx\t4\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\t2\tx
x\t1\t1\t3\tx\t3\tx\t1\tx\t1\tx\t1\t1\t3\tx\t1\t2\t1\tx\t3\tx\t1\t1\t4\tx\t2\t1\t2\t1\t5\tx\t1\t2\t1\t5\t1\tx\t1\t1\t4\tx\t2\t1\t1\t1\t1\t1\t1\tx\t1\t7\t3\t2\t1\tx\t1\tx\t3\tx\t2\t5\t1\t1\t3\t2\t1\tx\t1\tx\t1\t6\t1\t7\t2\tx\t1\tx\t3\t6\t5\tx\t6\t1\t2\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t5\tx
x\t1\tx\t1\tx\t1\tx\t6\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\t3\t1\t1\t1\tx\tx\tx\tx\tx\tx\tx\t7\tx\t2\tx\t1\tx\t5\tx\tx\t1\t1\t2\t1\tx\t3\tx\tx\t1\t3\t1\tx\tx\tx\tx\t3\t1\t1\t1\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx
x\t1\tx\t8\tx\t1\t1\t2\t6\t6\t1\t2\tx\t6\tx\t1\tx\t1\tx\t2\t1\t1\tx\t3\t2\t1\tx\t1\t1\t1\tx\t1\tx\t2\tx\t7\tx\t1\tx\t1\tx\t1\t1\t2\t1\t1\t3\t1\tx\t1\tx\t3\tx\t2\tx\t1\t1\t2\tx\t1\tx\t1\t1\t1\t1\t1\tx\t2\t1\t1\t1\t3\t1\t1\t1\t1\t2\t1\t2\t1\t1\t2\t1\t6\t2\t5\tx\t1\t1\t6\tx\t4\t3\t1\t1\t1\t1\t1\t3\t2\tx
x\t4\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t4\tx\t1\tx\t1\tx\t2\tx\t1\tx\tx\tx\t1\tx\t1\tx\t2\tx\t7\tx\t3\tx\t1\tx\t1\tx\t1\t1\t1\t2\t1\t3\t1\tx\t6\tx\t1\tx\t1\tx\t1\tx\t2\tx\t1\tx\t2\tx\tx\tx\tx\tx\t3\tx\tx\t1\t1\t1\t6\tx\tx\tx\t1\t1\t1\t3\t1\tx\tx\t1\t1\t7\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx
x\t1\tx\t2\t1\t1\t1\t1\t1\t1\tx\t2\t1\t1\tx\t1\t3\t1\t3\t1\tx\t6\t2\t1\t1\t1\t1\t1\tx\t1\t6\t3\t1\t1\tx\t1\tx\t1\t2\t3\t5\t1\t1\t1\t1\t2\t1\t5\t1\t1\tx\t2\t4\t3\t2\t1\tx\t2\tx\t5\tx\t1\t1\t1\t1\t1\tx\t2\tx\t1\t1\t6\t1\t2\tx\t1\t1\t1\t2\t1\t1\t1\tx\t1\t4\t1\t1\t3\t1\t1\tx\t1\t1\t1\t2\t1\tx\t2\tx\t1\tx
x\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\t1\tx\t5\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t4\tx\t4\t1\t7\tx\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\t1\t1\t2\t3\tx\t2\t1\t2\t1\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx
x\t5\t1\t2\tx\t1\t7\t5\t2\t1\t1\t6\tx\t1\t1\t1\t4\t2\tx\t1\tx\t1\t2\t1\t1\t3\tx\t1\tx\t1\t3\t3\t2\t1\t1\t1\t1\t2\t1\t1\tx\t1\t2\t4\t1\t1\tx\t1\t1\t1\t2\t1\tx\t3\t1\t1\tx\t1\t1\t6\tx\t1\t3\t1\tx\t7\t1\t2\t2\t1\tx\t1\t1\t1\tx\t2\t3\t1\tx\t1\tx\t3\tx\t1\t1\t1\t4\t3\tx\t1\tx\t1\t2\t1\t3\t1\t1\t1\tx\t1\tx
x\t2\tx\t2\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\tx\t1\tx\tx\tx\t1\tx\t1\t3\t1\tx\t5\tx\t2\tx\tx\tx\t2\tx\t3\t1\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t3\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\t3\tx\t1\tx\t3\tx\t1\tx\tx\tx\t1\tx\t1\tx\t4\tx
x\t7\tx\t4\t3\t1\tx\t1\t4\t1\tx\t1\t1\t3\t1\t1\t1\t3\tx\t5\tx\t6\tx\t1\t1\t1\t1\t1\t6\t1\tx\t1\t2\t1\tx\t1\t1\t1\t1\t6\t3\t1\tx\t2\t5\t2\t4\t3\t4\t6\tx\t1\tx\t2\t3\t1\tx\t2\tx\t1\t1\t3\t3\t6\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t2\t2\t1\t1\tx\t1\t1\t1\t1\t1\tx\t3\tx\t2\t1\t2\tx\t8\tx\t1\t1\t2\tx\t7\t6\t2\tx
x\t4\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\t1\t2\t2\t3\tx\t7\tx\t1\tx\t1\tx\t1\t2\t1\tx\tx\tx\t3\tx\tx\tx\t5\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\t2\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t6\tx\tx\tx\tx\tx\tx\tx\t2\tx\t6\tx\tx\tx\t2\tx\tx\tx\t3\tx\tx\tx
x\t2\t1\t3\tx\t1\t1\t2\tx\t1\t1\t3\t2\t5\t1\t1\t1\t1\tx\t1\t1\t1\t1\t2\t6\t1\tx\t3\tx\t4\t7\t1\tx\t8\tx\t1\tx\t1\t1\t2\tx\t8\tx\t1\t6\t7\t3\t1\t1\t1\tx\t1\t1\t2\t1\t2\t1\t1\tx\t8\tx\t2\t2\t2\t3\t7\tx\t3\t3\t1\t5\t1\t3\t1\t4\t1\t1\t1\t2\t1\t2\t1\tx\t3\t3\t1\tx\t3\tx\t1\tx\t6\t7\t4\tx\t1\t1\t1\t1\t1\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\t4\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\t2\t1\t2\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\t5\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\t1\t2\t5\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t2\tx\tx\tx\t1\tx
x\t1\t5\t6\t1\t1\t1\t4\t1\t1\tx\t2\tx\t2\t3\t1\t1\t8\tx\t1\t1\t2\t1\t1\tx\t1\t6\t1\t1\t1\t3\t1\tx\t1\t3\t7\tx\t1\tx\t2\t1\t4\tx\t3\tx\t1\t2\t3\t1\t2\t3\t1\t2\t1\tx\t2\tx\t4\t1\t3\t1\t1\t1\t2\tx\t2\t1\t3\t1\t2\tx\t1\t3\t1\t2\t2\t1\t3\tx\t2\t2\t1\tx\t7\tx\t3\t1\t1\tx\t1\t1\t4\t1\t1\tx\t1\t7\t3\tx\t2\tx
x\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\t1\t1\t2\t1\tx\t3\t1\t1\t1\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\t1\t7\t1\t3\tx\t3\tx\t1\t1\t1\t1\tx\tx\tx\tx\tx\t1\t1\t1\t2\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\t7\tx\t2\tx\tx\tx\tx\tx\tx\tx
x\t2\t5\t1\t2\t1\tx\t1\tx\t2\t2\t1\t1\t1\tx\t1\t3\t1\t1\t1\t1\t4\t1\t1\t4\t1\t5\t1\t2\t1\tx\t7\tx\t1\tx\t3\t2\t3\t1\t1\t1\t6\t1\t2\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t6\tx\t1\t1\t1\t3\t1\tx\t1\t5\t3\t1\t1\t1\t1\t4\t1\tx\t2\tx\t1\tx\t3\tx\t2\tx\t2\t1\t1\t2\t1\tx\t5\t6\t1\t3\t1\tx\t1\t3\t3\tx\t1\t1\t1\tx
x\t2\tx\t7\tx\tx\tx\t1\tx\t2\tx\tx\tx\t5\tx\t2\tx\tx\tx\tx\t2\t1\t2\tx\tx\t1\t3\t1\t5\t1\tx\t2\tx\t7\tx\t4\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\t1\tx\t2\t1\t2\t1\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\t4\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\t1\t2\t7\t1\tx\t1\t3\t1\t3\t1\t1\t1\tx\t1\t2\t2\t1\t1\t1\t3\t1\t1\tx\t1\t2\t1\tx\t1\tx\t1\t2\t1\tx\t3\t6\t1\t2\t3\tx\t1\t3\t1\tx\t2\t1\t1\t3\t1\t1\t3\t1\t1\tx\t3\t1\t6\t1\t1\t1\t1\tx\t1\t2\t7\t1\t1\tx\t7\t1\t1\t3\t1\t1\t1\tx\t1\tx\t2\t1\t1\tx\t1\t2\t1\tx\t3\t2\t1\t5\t2\tx\t1\tx
x\tx\tx\t3\tx\t1\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t5\tx\t1\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\t1\t2\t2\tx\tx\t1\tx\tx\tx\t1\tx\t3\tx\tx\tx\t1\tx\tx\tx\t3\tx\t3\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx
x\t2\t1\t1\t1\t1\t6\t3\t1\t1\t6\t1\t1\t3\t4\t6\tx\t2\tx\t3\t1\t1\tx\t1\t2\t7\tx\t2\tx\t3\tx\t1\tx\t1\tx\t1\t1\t7\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t2\t1\tx\t2\t2\t2\t1\t2\tx\t3\t1\t1\t3\t1\t1\t1\t1\t1\tx\t3\t6\t1\t2\t1\tx\t1\t1\t2\t7\t1\tx\t1\t1\t1\tx\t4\t1\t1\t1\t1\tx\t1\t2\t1\tx\t1\t2\t1\t1\t1\tx\t8\tx
x\tx\tx\tx\tx\t1\t3\t1\t1\t2\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\tx\tx\tx\t6\t1\t2\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t2\t6\t1\t1\tx\tx\tx\t1\t5\t2\tx\tx\tx\tx\tx\tx\t1\t7\t1\t1\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\t1\t1\t1\tx\tx\t1\tx
x\t6\t1\t1\t1\t3\t2\t1\t1\t3\t6\t3\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\t2\t2\t1\t1\tx\t3\tx\t2\t1\t1\tx\t1\t2\t1\t1\t1\tx\t1\t5\t1\t1\t1\t1\t7\t1\t1\t1\t2\t5\t6\t3\t1\t2\t1\t1\t1\tx\t1\t2\t1\tx\t1\t2\t2\tx\t1\t1\t1\tx\t1\t1\t1\tx\t3\tx\t1\tx\t1\t6\t1\tx\t2\t2\t1\tx\t2\tx\t2\t2\t1\t4\t3\t1\t7\t1\t1\tx\t2\tx
x\tx\tx\tx\tx\t2\t1\t4\t1\tx\tx\tx\tx\tx\t1\t1\t1\t2\t1\t1\tx\tx\tx\t2\t2\t1\tx\t1\tx\tx\tx\t4\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t5\tx\t6\t1\t2\t2\t3\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\t5\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\t1\t1\t1\tx\tx\t3\tx
x\t8\t2\t1\tx\t3\tx\t1\t2\t1\t1\t1\t5\t1\t3\t1\t1\t2\t1\t1\t3\t1\t1\t1\tx\t2\t1\t1\tx\t1\t2\t1\t1\t1\t1\t1\t2\t2\t1\t1\tx\t5\tx\t1\t1\t1\tx\t1\tx\t3\tx\t1\t3\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t8\t7\t5\tx\t2\tx\t1\tx\t1\tx\t2\t1\t1\tx\t1\t4\t1\tx\t1\tx\t1\t1\t1\tx\t6\tx\t1\tx\t3\t2\t1\tx\t2\t4\t5\tx\t1\tx
x\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t7\t1\t1\tx\tx\t2\tx\t6\tx\tx\tx\t3\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t4\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\t2\tx\t3\tx\tx\tx\t1\tx\t3\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t6\tx\t1\tx
x\t2\t3\t1\tx\t2\t1\t1\tx\t2\tx\t1\t1\t3\tx\t1\tx\t1\t1\t2\t1\t1\tx\t3\tx\t1\tx\t1\tx\t1\tx\t1\t2\t1\t1\t2\tx\t2\t2\t1\t3\t7\tx\t1\tx\t1\tx\t7\tx\t2\tx\t1\t1\t2\tx\t1\tx\t5\t2\t2\t3\t1\tx\t2\t1\t3\t1\t1\tx\t4\tx\t1\t1\t2\tx\t1\t2\t1\tx\t1\tx\t3\t2\t1\t1\t1\t1\t5\tx\t4\t1\t4\t1\t1\tx\t3\t2\t7\t1\t1\tx
x\t1\t1\t3\tx\tx\tx\t3\tx\t3\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t2\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx
x\t3\t1\t5\tx\t2\t1\t2\t1\t1\t3\t5\t1\t2\tx\t1\t1\t1\tx\t3\tx\t4\t7\t3\tx\t1\t1\t1\t2\t2\t1\t1\tx\t2\t1\t1\t1\t1\t2\t3\t1\t1\tx\t3\t2\t2\t2\t2\t1\t2\t3\t1\tx\t4\t1\t1\t3\t1\t5\t1\tx\t1\t1\t1\tx\t1\tx\t2\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t2\t6\tx\t1\tx\t7\t2\t1\tx\t1\tx\t1\tx\t1\t2\t4\t1\t1\t1\t1\tx\t2\tx
x\t1\t1\t1\tx\tx\tx\t2\tx\tx\tx\t3\tx\t6\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t6\tx\tx\tx\t6\tx\t1\tx\t1\t1\t1\t1\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx
x\t2\t1\t1\tx\t3\tx\t1\tx\t1\t4\t5\t1\t2\t1\t1\tx\t3\t3\t1\t1\t1\tx\t1\tx\t3\tx\t1\t7\t1\tx\t2\tx\t1\t1\t1\t1\t2\tx\t1\tx\t1\t2\t1\t1\t1\tx\t8\t6\t1\t1\t1\tx\t1\tx\t3\t1\t1\t2\t3\tx\t2\t6\t2\tx\t3\t1\t2\t4\t5\tx\t1\tx\t7\t1\t1\t1\t1\t1\t6\tx\t7\t7\t1\tx\t2\t1\t5\t1\t2\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx
x\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\t1\t1\t5\t1\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\t5\t3\t1\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t7\tx\t2\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t3\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx
x\t1\t6\t5\t2\t3\t1\t1\tx\t1\t1\t1\t2\t3\t2\t1\t3\t1\tx\t1\tx\t2\t1\t1\t5\t1\t2\t5\t2\t2\t1\t1\t3\t1\tx\t1\t1\t3\t1\t2\tx\t1\t1\t1\tx\t1\t2\t6\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\t3\t1\t1\t2\t1\t4\tx\t1\t3\t3\tx\t3\tx\t1\t1\t1\t2\t7\t2\t2\tx\t1\tx\t2\t1\t1\t1\t1\tx\t1\tx\t1\t2\t1\t2\t1\tx\t3\tx
x\tx\tx\t1\tx\tx\tx\t2\tx\t5\tx\tx\t2\t1\t5\t1\tx\tx\tx\t3\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\tx\tx\tx\t1\tx\t1\tx\tx\t1\t1\t1\t1\tx\t3\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\t2\tx\t1\tx\t2\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx
x\t1\t1\t1\t1\t1\tx\t2\t1\t3\tx\t2\t1\t2\tx\t1\t1\t4\tx\t3\t1\t2\tx\t2\t5\t2\tx\t1\t3\t1\t1\t3\tx\t8\tx\t1\t3\t3\t3\t3\tx\t6\t1\t1\t2\t5\tx\t1\t3\t1\t1\t2\t5\t1\t1\t1\t5\t1\tx\t7\tx\t5\t1\t2\t3\t3\tx\t1\tx\t1\tx\t2\t1\t1\tx\t1\t3\t7\tx\t1\t1\t2\tx\t7\t2\t2\t6\t5\t1\t2\tx\t2\tx\t4\t1\t1\tx\t1\tx\t1\tx
x\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\t1\t1\t5\t1\tx\tx\tx\t1\tx\t3\tx\tx\tx\t5\tx\tx\tx\tx\t3\t1\t1\t2\tx\tx\t1\t3\t1\t3\tx\t4\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t6\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\t3\t1\t1\tx\tx\t1\tx\tx\tx\tx\tx\t4\tx\t3\tx
x\t1\t5\t1\tx\t1\tx\t1\t2\t1\tx\t1\tx\t3\tx\t6\t1\t1\t1\t8\tx\t1\tx\t6\t2\t1\t5\t1\tx\t1\t2\t1\tx\t1\tx\t1\t1\t1\t1\t4\tx\t2\t1\t7\t2\t2\t6\t1\t1\t1\t1\t2\tx\t7\t4\t1\t1\t2\tx\t2\t1\t7\tx\t3\tx\t1\tx\t1\tx\t8\tx\t1\tx\t2\tx\t1\t2\t1\tx\t1\tx\t4\t1\t2\t2\t1\t1\t1\t7\t2\t2\t1\t3\t7\tx\t1\tx\t3\t1\t1\tx
x\tx\tx\t1\tx\tx\tx\t3\tx\t1\tx\t1\tx\t2\tx\t2\tx\t1\tx\tx\t4\t1\t1\t1\t1\t2\t5\t1\tx\t1\tx\t1\tx\t4\tx\t2\tx\tx\tx\t1\tx\tx\t1\t1\t1\t1\tx\t1\t1\t3\t3\t2\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx
x\t1\t1\t3\tx\t1\tx\t1\tx\t1\t1\t1\t5\t6\tx\t1\tx\t1\tx\t3\t1\t1\t1\t3\t2\t1\t5\t1\tx\t1\tx\t1\tx\t6\tx\t1\tx\t1\t2\t3\t1\t1\t1\t1\t2\t6\t1\t1\tx\t1\tx\t2\t7\t1\tx\t1\t2\t1\t1\t1\t5\t2\t1\t7\t3\t3\t1\t1\tx\t1\t7\t1\tx\t1\tx\t5\tx\t8\tx\t1\t3\t2\t1\t5\t2\t1\tx\t1\t1\t2\tx\t1\t2\t1\t1\t3\tx\t1\tx\t2\tx
x\t5\tx\t1\tx\t3\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\t1\t1\t1\t1\t1\t2\t5\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t2\t3\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t3\tx\t1\tx\t1\tx\t1\tx\tx\tx\t3\tx\tx\t1\t1\t1\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t3\tx
x\t2\tx\t2\tx\t3\t1\t2\tx\t1\tx\t7\t1\t3\t1\t1\tx\t1\t1\t2\t3\t1\t1\t3\t2\t6\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\t2\t1\t7\t1\tx\t2\tx\t1\tx\t1\t7\t1\t1\t1\tx\t1\tx\t2\tx\t1\tx\t1\t1\t1\tx\t2\tx\t2\t4\t1\t1\t1\t1\t1\tx\t3\t1\t1\t3\t1\tx\t1\t3\t4\tx\t6\t1\t1\tx\t1\t6\t2\t6\t3\t4\t2\tx\t1\tx\t1\t7\t3\t1\t1\tx
x\t5\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t3\tx\t3\tx\tx\t2\t1\t1\t1\tx\t1\tx\t7\tx\tx\tx\t1\tx\t1\tx\t2\tx\t1\tx\t2\tx\tx\tx\t5\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t6\tx\t1\t2\t1\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t3\tx\tx\tx\t1\t1\t1\t1\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t3\tx
x\t4\t1\t1\t5\t2\tx\t1\tx\t3\t4\t6\tx\t1\tx\t1\tx\t3\t1\t1\t1\t1\tx\t1\t1\t1\t3\t1\tx\t2\t2\t5\tx\t1\t1\t2\tx\t1\tx\t3\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t3\tx\t1\tx\t3\tx\t6\tx\t1\tx\t1\t2\t1\tx\t1\tx\t1\tx\t1\t2\t1\tx\t7\tx\t4\tx\t2\t1\t2\tx\t1\t2\t1\t2\t1\tx\t1\t1\t1\tx\t8\tx\t2\t4\t3\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\t3\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\t6\t1\t3\t2\t1\t1\t4\t1\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t3\tx\tx\tx\t1\tx\t3\t7\t1\t1\t7\t1\t1\t1\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx
x\t2\tx\t1\tx\t3\t1\t1\t1\t3\tx\t1\t1\t1\t1\t1\t5\t1\t1\t1\t1\t1\tx\t6\t2\t1\t2\t1\t1\t3\t1\t1\tx\t5\t3\t3\t1\t1\t1\t2\tx\t1\t2\t1\t2\t6\t1\t1\t2\t3\tx\t2\t1\t1\t2\t2\t1\t1\t6\t7\t1\t1\t5\t1\t4\t2\t2\t4\t1\t3\tx\t1\t1\t1\tx\t1\tx\t1\t1\t6\tx\t1\t1\t1\t1\t1\tx\t1\t1\t5\t1\t1\t1\t1\tx\t2\tx\t1\tx\t1\tx
x\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\t1\tx\t3\tx\t4\tx\t1\tx\t3\tx\t5\t3\t1\t1\tx\tx\t1\t1\t1\t1\t1\t1\t7\t1\t1\tx\tx\tx\t7\tx\t1\tx\tx\tx\tx\tx\t7\t1\t1\t3\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\t1\t2\t1\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t3\tx\t3\tx\t5\tx
x\t2\t1\t2\tx\t1\t2\t8\tx\t1\tx\t4\tx\t1\tx\t2\t1\t7\tx\t1\tx\t2\tx\t1\tx\t1\tx\t3\tx\t1\tx\t3\tx\t3\tx\t1\t1\t2\t1\t1\t1\t3\t1\t1\t1\t1\t2\t4\t1\t7\t1\t1\t1\t1\t1\t1\tx\t1\t2\t1\t5\t3\tx\t1\t1\t1\tx\t4\t1\t1\t5\t1\t1\t1\t1\t4\tx\t1\t4\t2\tx\t1\t1\t2\t1\t1\t1\t1\t1\t1\t6\t1\t4\t3\t1\t3\tx\t1\tx\t1\tx
x\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\t1\t4\t1\tx\tx\t4\t1\t3\t7\t1\t2\t4\t2\tx\tx\t3\t3\t3\t1\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\t2\tx\t5\tx\t1\tx\t6\t7\t2\tx\t6\tx\t1\tx
x\t6\t6\t2\t1\t3\t2\t2\tx\t6\t1\t1\tx\t3\t4\t1\t1\t1\t1\t1\t5\t3\t1\t1\t1\t1\tx\t1\tx\t2\t1\t1\tx\t6\t1\t4\t1\t1\t1\t2\t3\t7\t1\t1\tx\t1\t1\t1\tx\t1\t3\t1\t2\t1\t3\t1\t1\t1\t1\t1\t2\t4\tx\t1\t3\t1\t1\t2\t1\t1\t1\t1\tx\t2\t3\t1\tx\t6\t2\t3\tx\t2\tx\t3\tx\t1\tx\t2\tx\t5\tx\t2\tx\t1\t4\t1\tx\t1\t3\t5\tx
x\tx\t2\t1\t2\t2\t1\t1\tx\tx\tx\t1\tx\tx\tx\t1\t1\t1\t1\t3\tx\tx\tx\t3\tx\tx\tx\t1\tx\t7\tx\tx\tx\t1\tx\t1\t1\t1\t1\t1\t2\t7\t1\t1\tx\t1\tx\tx\tx\t2\t1\t3\t1\t2\t4\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t5\tx\t3\tx\t2\tx\tx\tx\tx\tx\t2\t2\t1\tx\t5\tx\t1\tx
x\t1\t1\t5\t1\t1\t1\t2\tx\t7\t2\t3\t1\t1\tx\t1\t1\t3\t2\t1\tx\t1\t2\t1\t2\t1\tx\t2\t1\t1\t2\t6\t3\t7\t2\t6\t1\t1\t3\t3\t1\t1\t5\t1\t5\t1\t1\t8\tx\t1\t3\t1\t1\t1\t1\t7\t1\t1\tx\t2\t1\t2\tx\t5\t6\t2\t1\t1\t1\t1\t2\t1\t1\t4\t1\t1\tx\t1\t1\t1\t7\t3\tx\t1\tx\t2\t1\t2\t1\t1\t1\t1\tx\t1\t5\t1\tx\t3\tx\t1\tx
x\tx\t2\t1\t1\t7\t2\t5\tx\tx\tx\tx\tx\t1\tx\tx\t1\t1\t1\t1\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\t2\t1\t3\t1\t2\t2\t1\t3\t1\t2\tx\tx\tx\tx\tx\t2\t2\t1\t1\t2\t2\t1\tx\t7\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t1\t3\t4\t1\t1\tx\tx\tx\tx\tx\t1\tx
x\t3\t1\t1\t1\t3\t1\t1\tx\t1\tx\t1\t1\t1\tx\t3\t1\t1\t1\t1\t1\t1\tx\t1\t5\t2\t1\t3\t1\t3\t2\t4\t5\t2\t1\t2\t2\t1\t1\t1\t2\t1\tx\t2\t6\t7\tx\t6\t2\t1\t1\t1\t1\t1\t1\t1\tx\t1\tx\t3\t2\t1\tx\t2\t1\t3\tx\t7\tx\t1\t3\t1\tx\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t7\t1\t1\tx\t1\t3\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\t7\tx
x\t1\tx\t3\tx\t5\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\t1\t3\t4\t4\t6\tx\t4\t1\t1\t2\tx\tx\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\t2\t1\t1\t2\t1\tx\tx\t2\tx\t5\t2\t2\t1\t1\t1\tx\tx\tx\tx\tx\tx\t2\tx
x\t3\tx\t1\tx\t1\t3\t2\t1\t1\tx\t3\t2\t1\tx\t1\tx\t2\t6\t3\tx\t1\tx\t4\t1\t2\tx\t2\t2\t8\tx\t1\tx\t1\tx\t1\tx\t7\t6\t1\t7\t5\tx\t1\t1\t1\t1\t1\tx\t1\t1\t2\t1\t2\t5\t1\t1\t2\t1\t2\t2\t1\tx\t1\t1\t1\tx\t7\t1\t1\t1\t3\tx\t6\tx\t1\t1\t2\t7\t1\t2\t1\t1\t1\tx\t2\tx\t3\t1\t1\t1\t1\t7\t1\t1\t1\t1\t3\t2\t1\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\t1\t1\t1\t1\tx\tx\tx\t7\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t3\t1\t1\t5\t1\tx\t1\tx\tx\t2\t1\t1\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t6\tx\t1\tx\t1\tx\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\t2\tx\t2\tx\tx\tx\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx
x\t3\t1\t2\tx\t1\t1\t1\t1\t6\tx\t1\t1\t1\t3\t1\t1\t2\t1\t1\tx\t1\t1\t4\t2\t4\t1\t1\tx\t1\t2\t5\tx\t3\t1\t1\t4\t1\t1\t1\t1\t1\t1\t1\tx\t2\t1\t2\tx\t1\t1\t1\t2\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t2\t2\t1\t1\t3\t3\tx\t5\t2\t6\tx\t1\tx\t8\tx\t3\t1\t1\t1\t1\t3\t3\t1\t5\tx\t1\tx\t6\tx\t2\tx\t5\t1\t1\t1\t1\tx
x\tx\tx\t3\tx\t1\tx\tx\tx\t1\tx\t1\t5\t3\t1\t1\t1\t1\tx\tx\tx\tx\tx\tx\tx\t1\t5\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t5\t1\t1\t5\t3\tx\t1\tx\t1\tx\t2\tx\tx\t2\t3\t3\tx\tx\t7\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t4\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx
x\t8\tx\t2\t1\t1\t3\t1\tx\t2\t2\t7\t1\t1\t2\t3\t1\t1\t2\t7\t2\t1\t2\t1\t2\t1\t1\t3\t1\t3\tx\t1\t3\t1\t3\t1\tx\t1\t3\t1\t1\t1\t3\t1\t4\t1\tx\t3\tx\t1\tx\t3\t1\t1\t1\t1\t1\t1\tx\t3\t3\t2\tx\t8\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t7\tx\t4\tx\t6\t1\t1\t1\t1\tx\t4\tx\t3\t3\t1\tx\t2\tx\t1\tx\t1\tx\t1\tx\t3\tx
x\t2\tx\tx\t2\t3\t6\t1\tx\t1\tx\tx\tx\tx\tx\t1\t1\t3\tx\tx\tx\t1\tx\t1\tx\t1\t1\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\t1\t1\t1\t3\t1\t4\t7\t1\tx\t3\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx\t5\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t3\tx
x\t1\tx\t1\t1\t7\t1\t1\tx\t1\tx\t4\t5\t1\t1\t1\t1\t1\t1\t1\t5\t4\tx\t1\tx\t4\t1\t1\tx\t1\t1\t1\t3\t1\tx\t1\t1\t1\t7\t1\t1\t2\t1\t1\t4\t3\t1\t4\tx\t1\t1\t1\tx\t2\tx\t3\t1\t1\t1\t2\tx\t1\t1\t1\t2\t1\tx\t1\tx\t1\t1\t1\t2\t1\t1\t2\tx\t1\t2\t5\tx\t3\tx\t7\t1\t4\tx\t3\t1\t3\tx\t1\t1\t3\t1\t2\t2\t1\tx\t4\tx
x\t3\tx\tx\t1\t3\t3\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t5\tx\t2\t7\t6\t1\t4\tx\t1\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\t7\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t7\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx
x\t1\tx\t5\t3\t2\t2\t1\t2\t1\t1\t5\t3\t3\tx\t5\t1\t1\t1\t3\tx\t1\t1\t4\t1\t3\tx\t1\t1\t5\tx\t1\tx\t1\t1\t2\t1\t1\t1\t2\t2\t1\tx\t1\tx\t1\t1\t4\t1\t1\t1\t2\t3\t1\t1\t5\tx\t3\t2\t7\tx\t1\tx\t2\tx\t1\t1\t1\tx\t1\tx\t5\t1\t1\tx\t1\t1\t1\t1\t1\t2\t6\tx\t2\t5\t1\t7\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\t4\t1\tx
x\t3\tx\tx\tx\t1\tx\t1\t1\t2\t2\tx\tx\t2\tx\tx\tx\t6\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t7\tx\t1\tx\t3\tx\tx\tx\tx\tx\t2\tx\tx\tx\t2\t2\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t5\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx
x\t1\t1\t3\tx\t1\t7\t3\t2\t2\t6\t5\t3\t1\t1\t2\t1\t1\tx\t2\t1\t2\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx\t1\tx\t2\t1\t1\t2\t2\t2\t2\tx\t1\t2\t3\tx\t1\tx\t4\tx\t1\t2\t2\tx\t1\t2\t1\t2\t1\tx\t3\t1\t1\t3\t1\t1\t5\t5\t1\tx\t1\t1\t1\tx\t1\tx\t2\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t3\tx\t6\t1\t1\tx
x\t6\tx\t2\tx\t1\tx\tx\tx\t7\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t3\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\t3\t4\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t4\tx\tx\tx\tx\tx\t3\t1\t1\t7\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\t3\t2\t1\t3\tx
x\t1\tx\t1\t1\t2\tx\t8\tx\t1\tx\t2\t1\t1\t5\t1\tx\t1\t1\t1\tx\t7\t1\t1\t3\t1\tx\t7\t3\t4\t7\t4\t1\t2\t2\t1\t1\t1\tx\t1\t1\t3\tx\t1\t1\t3\t2\t1\tx\t3\tx\t1\tx\t7\t2\t1\t1\t3\t1\t1\t1\t1\t1\t1\t1\t1\tx\t2\t2\t1\t5\t1\tx\t1\tx\t1\t1\t2\t1\t1\t3\t6\tx\t2\t1\t2\tx\t1\tx\t3\tx\t1\tx\t1\t1\t2\t1\t2\t1\t7\tx
x\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t4\tx\t2\t1\t2\t1\t6\t1\t1\t5\tx\tx\t3\tx\t1\tx\tx\tx\t3\t1\t1\tx\t1\tx\t1\tx\t2\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t4\tx\tx\tx\t1\tx\t2\tx\t2\tx\t2\tx\t3\tx\tx\t1\t1\t7\t1\tx
x\t1\t2\t1\tx\t6\t2\t2\t1\t6\tx\t1\t3\t7\t1\t2\tx\t7\tx\t1\t3\t2\t1\t4\tx\t3\tx\t3\t1\t1\t1\t1\t1\t1\t5\t1\t3\t3\tx\t1\t1\t1\t2\t1\t1\t6\t1\t1\tx\t3\tx\t3\t4\t3\t1\t1\tx\t3\tx\t1\tx\t3\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t3\t1\t6\t2\t1\t1\t1\t1\tx\t2\tx\t1\t3\t1\t1\t4\tx\t1\t1\t3\t1\t1\t1\t2\t1\t1\t3\t1\tx
x\t7\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\t3\tx\t5\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\t1\t1\t1\t1\tx\t1\tx\t5\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t4\tx\tx\tx\t3\tx\t1\t1\t1\t1\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t6\t1\t2\t7\t1\tx
x\t1\t1\t1\tx\t1\tx\t2\tx\t1\t3\t1\tx\t4\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\t2\t3\tx\t1\t1\t1\t1\t2\tx\t1\t1\t1\t1\t3\tx\t1\t1\t2\tx\t1\t1\t8\tx\t1\tx\t1\t2\t1\t3\t1\t1\t1\tx\t1\tx\t1\t2\t1\t5\t1\tx\t1\t6\t2\t1\t5\t2\t1\t5\t3\t1\t1\tx\t2\t2\t2\t2\t3\tx\t1\t1\t1\t1\t1\tx\t1\tx\t3\t1\t1\tx\t1\t1\t1\t3\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\t1\t1\t1\t1\tx\t2\t4\t1\t1\t1\tx\tx\tx\t1\tx\t4\tx\t1\tx\tx\tx\t1\t1\t3\t2\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\t1\t3\t2\t1\tx\tx\tx\t1\t1\t4\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t5\tx\tx\tx\t2\tx\tx\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\t2\t1\t1\t1\t1\t1\t2\tx\t1\t1\t1\t1\t3\t1\t1\t1\t2\t5\t2\t1\t1\tx\t1\tx\t1\t1\t2\t1\t2\t1\t1\t1\t6\tx\t1\tx\t3\t2\t1\tx\t3\tx\t6\tx\t5\t2\t6\tx\t1\tx\t3\t2\t1\t1\t2\t1\t1\t1\t1\tx\t2\t1\t1\t1\t2\t5\t1\t1\t3\t3\t1\tx\t2\tx\t1\t2\t2\t7\t5\tx\t3\tx\t1\t5\t1\tx\t1\tx\t1\t1\t7\tx
x\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\t2\t1\t1\t1\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t2\t1\t2\tx\tx\tx\t5\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t3\t1\t5\t5\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t5\t3\t1\tx\tx\tx\t3\t3\t2\t1\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx
x\t3\tx\t1\tx\t1\t1\t2\tx\t4\t2\t3\t1\t1\t1\t1\t1\t1\tx\t2\tx\t1\t1\t1\t1\t3\tx\t2\t3\t3\tx\t2\tx\t4\t1\t6\t1\t5\tx\t1\t1\t1\tx\t1\t1\t1\t5\t1\tx\t1\t1\t2\tx\t1\tx\t1\t3\t1\t1\t1\t4\t1\t1\t1\tx\t7\t1\t1\t1\t2\tx\t3\t1\t2\tx\t1\tx\t7\t1\t3\t1\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t3\tx\t5\t1\t1\t2\t1\tx
x\t3\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\t1\t2\t4\t3\tx\t6\tx\t1\tx\tx\tx\t1\t1\t1\tx\t6\t1\t1\tx\t2\tx\t1\tx\tx\tx\t1\t3\t1\t3\t3\tx\tx\tx\t1\tx\t3\t3\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\t2\t1\t1\t6\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\t2\t1\t1\t7\tx\tx\tx\t1\tx\t7\tx\tx\tx\t1\tx\t1\tx
x\t1\tx\t1\t1\t1\t1\t3\tx\t1\tx\t4\tx\t1\t1\t1\tx\t2\tx\t1\tx\t2\tx\t1\t1\t2\tx\t2\t2\t6\t3\t1\t1\t1\t3\t5\tx\t3\t2\t3\t1\t1\t3\t4\t1\t1\t1\t3\t1\t6\t6\t1\t1\t3\t1\t1\tx\t1\tx\t2\tx\t1\t2\t1\tx\t2\tx\t1\t1\t4\t1\t1\tx\t1\t1\t3\tx\t5\t2\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t6\t3\t3\tx\t3\t1\t1\tx\t1\tx\t3\tx
x\tx\tx\tx\tx\tx\tx\t3\tx\t1\tx\t1\tx\tx\tx\t3\tx\tx\tx\t2\tx\t1\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t3\t2\t1\t1\t3\tx\tx\tx\t1\tx\t1\t1\t3\tx\t2\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t5\tx\t5\t7\t1\t1\t1\tx\t1\tx\t1\tx\t2\tx\t2\tx\t1\tx\tx\tx\t1\tx\t6\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx
x\t8\tx\t1\t1\t3\tx\t5\tx\t1\t3\t2\t1\t1\t1\t1\t6\t2\t3\t1\tx\t1\tx\t1\tx\t1\t2\t1\tx\t3\t2\t7\t1\t3\tx\t3\tx\t1\t1\t1\t2\t1\tx\t1\t2\t1\t1\t3\t1\t3\t2\t1\t3\t1\tx\t1\t1\t1\t2\t2\t5\t1\tx\t3\t3\t2\t1\t3\t1\t1\t1\t1\tx\t3\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t3\tx\t1\tx\t5\tx\t1\t1\t1\tx\t3\t5\t1\tx\t8\tx
x\t1\tx\tx\tx\t2\tx\t2\tx\t1\tx\t5\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t3\tx\t2\t2\t2\t3\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\t3\t1\t1\t1\tx\t1\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\t4\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\t1\t1\t1\t1\t1\t1\t7\tx\t1\tx\t1\tx\t1\t3\t1\t5\t3\tx\t1\tx\t1\t3\t1\t3\t1\t1\t1\t5\t1\tx\t1\t2\t3\tx\t2\t2\t3\tx\t2\tx\t1\tx\t1\tx\t2\tx\t6\t2\t1\t1\t1\t2\t1\t2\t4\t1\t1\t2\t7\t1\t1\tx\t8\t1\t3\t3\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t3\t7\t1\tx\t1\t1\t1\t5\t1\tx\t3\tx\t3\t1\t1\t1\t1\t1\t1\t2\t1\t1\t8\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
`;

const chestsAsObj = [
  {"x": 5, "y": 3, "bonus": 2, "amount": 8, "html":
`<b>И что, кому-то еще нужна математика?</b>
<p>Вообще мало кто может просто представить, сколько нужно математики, чтобы можно было на экране смартфона или ноутбука увидеть эту надпись.
Например, чтобы отобразить буквы, их нужно как-то «оцифровать».
Каждая буква в шрифте задаётся набором отрезков и кривых Безье (это называется «векторный шрифт»), которые нужно превратить в набор яркостей каждого пикселя на экране.
Здесь нужна геометрия и вычислительная геометрия.
<br>
Но перед этим этот текст должен добраться до вашего смартфона/компьютера.
Для этого он должен быть превращён в последовательность нулей и единиц и отправлен в виде радиосигнала от вашей точки доступа или от сотового оператора.
Тут не обойтись без преобразования Фурье и прочей математики работы с сигналами.
<br>
Но перед этим текст должен найти путь от нашего сервера в Санкт-Петербурге до вас через десяток других устройств.
Это невозможно сделать без развитой теории графов.
<br>
При этом сообщение будет зашифровано при помощи криптографии: теории чисел и теории групп.
<br>
А ссылку на страницу игры вы взяли в телеграм-боте.
Который вообще может быстро работать благодаря теории алгоритмов и теории сложности: информацию о миллионах пользователей можно почти мгновенно искать при помощи деревьев — это такая структура данных.
<br>
Если честно, то мы всё очень-очень упростили :)
Вот «Полная карта математики» из <a href="https://youtu.be/OmJ-4B-mS-Y" target="_blank">этого ролика</a>, переведённая на русский.
Только она очень не полна :)
Кликните на неё, чтобы увеличить.
<br> 
<a href="https://shashkovs.ru/i/math_map.jpg" target="_blank"><img style="width:100%" src="https://shashkovs.ru/i/math_map_s.png"/></a>
</p>`
  },
  {"x": 5, "y": 13, "bonus": 2, "amount": 8, "html":
`<p>Самые отвлечённо-умозрительные научные теории могут через какое-то время (порой — значительное!) стать основой весьма практических дел, причём выгода от только одного применения многократно окупает расходы на чудаков-математиков за всю историю науки...
<br>
Первая половина XIX века.
Ректор Казанского университета Николай Иванович Лобачевский предлагает свою «Воображаемую геометрию», в которой сумма углов треугольника не равна 180 градусам, как в существовавшей две тысячи лет геометрии Евклида. 
<br>
Начало XXI века. 
Для работы GPS-навигаторов нужны очень точные часы на спутниках орбитальной группировки, поддерживающих работу навигационной системы.
Ход часов в этих условиях изменяется благодаря сразу двум эффектам: большой скорости спутника и нахождению в гравитационном поле Земли. 
Это как про неевклидову геометрию пространства-времени. И если в какой-то момент «отключить» учёт этих эффектов, то уже за сутки работы в показаниях навигационной системы накопится ошибка порядка 10 км.
</p>`
  },
  {"x": 23, "y": 1, "bonus": 2, "amount": 8, "html":
`<p>Математика является и языком, и главным инструментом естественных наук и техники. Математика играет эту роль и в физике, от теории до приложений, и в осуществлении космических полётов, и в укрощении атомной энергии, и в жизни компьютерного мира. 
Менее очевидна важность математики в таких дисциплинах, как медицина или лингвистика. 
Но даже читатель, догадывающийся о значительной математической «составляющей» в различных сферах деятельности, не всегда может оценить степень зависимости этих областей от математики. 
Основная причина — сложность применяемых математических инструментов, часто — специально разработанных для конкретного приложения. 
И вообще люди редко задумываются над математической «начинкой» окружающих нас предметов и явлений, а иногда и просто не замечают её.</p>`
  },
  {"x": 5, "y": 19, "bonus": 2, "amount": 8, "html":
`<p>Современная биология ещё не может «прочитать» большие молекулы ДНК как книгу, «буква за буквой». 
Вместо этого учёные расшифровывают последовательности коротких кусочков ДНК, не зная, из какого места генома был вырезан данный кусочек. 
Процесс сборки генома из огромного числа таких кусочков, полученных из большого числа копий одной ДНК, называется секвенированием (от английского слова sequence — последовательность). 
Этот процесс сродни попытке собрать пазл из миллиарда кусочков и основывается на развитии одной математической теории, зародившейся три столетия назад.
<br>
Великий математик Леонард Эйлер решает «задачу о кёнигсбергских мостах» — доказывает, что в Кёнигсберге, расположенном на берегах реки и двух её островах, нельзя было пройти по каждому из семи мостов, существовавших в то время, ровно один раз и вернуться после этого в исходную точку. 
Подобный путь на соответствующем графе называется эйлеровым циклом. 
У задачи о существовании эйлерова цикла критерий разрешимости очень простой — из каждой вершины графа должно выходить чётное число рёбер. 
<br>
У нас на кружке было несколько таких задач.
<br>
Задача нахождения эйлерова цикла решается относительно быстро даже для очень большого графа, и именно она используется для склейки кусочков при секвенировании!
</p>`
  },
  {"x": 3, "y": 23, "bonus": 2, "amount": 8, "html":
`<p>
Компьютерная томография — одно из наиболее впечатляющих научных достижений XX века. 
Оно оказало революционное воздействие на всю современную медицину. 
За разработку компьютерной томографии А. Кормак и Г. Хаунсфилд были удостоены Нобелевской премии 1979 года в области медицины и физиологии. 
При снятии томограммы изучаемую часть тела человека микросдвигами перемещают сквозь кольцо сканирующего устройства. 
Сканер, состоящий из источника рентгеновского излучения и ряда детекторов, находится в корпусе, имеющем форму тора («бублика») и может вращаться в нём по кругу.
Рентгеновские лучи по-разному ослабляются разными тканями.
Если по набору ослаблений («интеграл от функции «коэффициент поглощения» по отрезку движения луча») в разных направлениях восстановить функцию, то получится понять, что там внутри человека.
С математической точки зрения восстановление функции на плоскости по её интегралам вдоль всевозможных прямых — классическая задача, решённая Иоганном Радоном в 1917 году. 
Но тем не менее высокая стоимость современных компьютерных томографов больше связана не с инженерной сложностью конструкций, а с зашитыми в них нетривиальными математическими алгоритмами,
представляющими основную коммерческую тайну.
</p>`
  },
  {"x": 43, "y": 1, "bonus": 2, "amount": 8, "html":
`<p>Многие страны столкнулись с серьёзной проблемой. Число пользователей дорог увеличилось настолько, что те перестали справляться с нагрузкой. 
<br>
Наивное представление о том, что для решения проблемы пробок достаточно увеличить количество дорог, было опровергнуто уже тогда. Математики придумали пример дорожной сети, в которой после ввода дополнительной дороги эффективность сети уменьшалась. Естественное желание автомобилистов использовать новую дорогу для выбора оптимального по времени маршрута неожиданно приводило к увеличению времени проезда для всех водителей!
См. пример в <a href="https://old.kvantik.com/art/files/pdf/2012-03.6-10.pdf" target="_blank">этой статье</a>.
Было разработано много интересных подходов к моделированию транспортных потоков с целью оптимального управления ими, 
но основой для всех предлагаемых решений являются два раздела прикладной математики — вычислительная гидродинамика и теория игр.
</p>`
  },
  {"x": 29, "y": 15, "bonus": 2, "amount": 8, "html":
`<p>Одной из важнейших областей применений математики является криптография — наука о шифрах, т.е. способах преобразования информации, позволяющих скрывать её содержание от посторонних. 
С развитием электронных коммуникаций криптография стала предметом интереса более широкого круга потребителей: возникла необходимость защиты технических, коммерческих, персональных и других данных, передаваемых по общедоступным каналам связи.
В последние десятилетия в криптографии стали появляться шифры, стойкость которых обосновывается сложностью решения чисто математических задач: разложения больших чисел на множители, решения показательных сравнений в целых числах и других. 
Стойкость шифров зависит также и от качества генераторов случайных чисел, порождающих ключи. 
Методы и результаты различных разделов математики (в частности, алгебры, комбинаторики, теории чисел, теории алгоритмов, теории вероятностей и математической статистики) используются как при разработке шифров, так и при их исследованиях, в частности, при поиске методов вскрытия шифров. 
Криптография является богатым источником трудных математических задач, а математика — одной из основ криптографии.
История показывает, что рано или поздно развитие математических методов и техники приводит к тому, что задачи, казавшиеся неразрешимыми, находят решение. 
</p>`
  },
  {"x": 1, "y": 43, "bonus": 2, "amount": 8, "html":
`<p>Всем известен формат бумаги A4 — его размеры 210×297 мм.
Но откуда взялись эти странные числа?
Почему 297, а не удобные 300мм?
Оказывается, отношение 297 к 210 примерно равно... √2!
У листа с таким отношением сторон имеется свойство, и в делопроизводстве, и в полиграфии: сложив его пополам, лучим лист с теми же пропорциями и, значит, также снова удовлетворяющий этому условию. 
С точки зрения геометрии, всё дело в том, что исходный прямоугольник и его половина подобны. 
А если листы подобны, то макет страницы, разработанный для одного из них, можно перенести на второй простым масштабированием.
<br>
В серии «А» в качестве листа АО взят лист, имеющий размеры 1189x841 мм. 
Размеры листа выбраны так, что его площадь (с большой точностью) равна одному квадратному метру. 
В повседневной жизни наиболее часто встречается формат бумаги А4. 
Длины сторон листа равны 297 и 210 мм, это примерно одна четвёртая часть длин сторон листа АО, площадь листа А4 — примерно 1/16 квадратного метра. 
При плотности стандартной офисной бумаги 80 грамм на квадратный метр, один лист весит около 5 грамм, а пачка из 500 листов — 2,5 килограмма.
</p>`
  },
  {"x": 17, "y": 33, "bonus": 2, "amount": 8, "html":
`<p>В железнодорожных составах и поездах метро, в отличие от автомобилей, в колёсной паре колёса жёстко сцеплены друг с другом осью и, соответственно, вращаются с одинаковой угловой скоростью. 
Но при повороте поезда длины путей, пройденных колёсами, будут отличаться: ведь в каждой точке поворота радиус окружности у внешнего рельса чуть больше, чем радиус внутреннего рельса. 
С другой стороны, по техническим требованиям проскальзывания колёс относительно рельсов быть не должно. 
Кажется, что отсутствие проскальзывания и разный «пробег» жёстко сцепленных колёс — несовместимые обстоятельства и что поезда просто не смогут поворачивать. 
Спасает геометрия: колёса делают не цилиндрическими, а в виде конусов.
См. <a href="https://etudes.ru/etudes/train-wheelset" target="_blank">статью с анимацией про колёсные пары</a>.
</p>`
  },
  {"x": 51, "y": 1, "bonus": 2, "amount": 8, "html":
`<p>Работа спутниковых антенн, в частности тех, которые принимают телевизионный сигнал, основана на оптическом свойстве параболы.
Парабола — это график квадратичной функции <em>у = ах² + Ьх + с</em> (в частности, <em>у = х²</em>).
Если на параболу падает поток лучей, параллельных оси симметрии, то, отразившись от параболы, лучи придут
в фокус параболы (это такая особая точка), причём придут одновременно.
Радиосигналы от спутника идут почти параллельно (они ведь на расстоянии больше 30000км (да, 30 тыс.км!)),
а в фокусе как раз располагается небольшой приёмник, который получает все сигналы, попавшие на тарелку-антенну.
См. <a href="https://etudes.ru/sketches/parabola-optic-property/" target="_blank">анимацию</a> и
<a href="https://etudes.ru/etudes/parabolic-antenna/" target="_blank">целую статью</a>.
</p>`
  },
  {"x": 45, "y": 15, "bonus": 2, "amount": 8, "html":
`<p>Если проследить по карте маршрут полёта самолёта из Москвы в Петропавловск-Камчатский, то можно заметить, что во время полёта самолёт забирается (по широте) высоко вверх.
<a href="https://yandex.ru/maps/-/CCUgaSdGSC" target="_blank">См. карту</a>. 
Кажется, что длина такого пути больше длины «прямого» пути, соединяющего на карте эти два города (координаты по широте близки: 55° 45' 21" с. ш. и 53° 1' с. ш.). 
Странно, ведь лишние сотни километров пути самолёта — дорогое удовольствие. 
Но и сервис «Яндекс.Карты» на запрос о расстоянии между этими городами тоже выдаёт выпуклую вверх кривую. 
Всё дело в том, что понятие кратчайшего расстояния неразрывно связано с той поверхностью, по которой оно измеряется.
(А-ха-ха, вы ведь уже читали сундук про «воображаемую геометрию»? Это снова она!)
<br>
Любая плоская карта представляет земную поверхность с искажениями. 
А рассмотрение соответствующих траекторий на глобусе позволит во всём разобраться.</p>`
  },
  {"x": 53, "y": 9, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 33, "y": 31, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 41, "y": 31, "bonus": 2, "asmount": 8, "html":
`<p></p>`
  },
  {"x": 7, "y": 65, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 19, "y": 55, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 73, "y": 3, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 1, "y": 77, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 65, "y": 15, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 33, "y": 53, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 75, "y": 13, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 59, "y": 31, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 7, "y": 85, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 85, "y": 9, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 47, "y": 49, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 1, "y": 97, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 99, "y": 1, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 29, "y": 73, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 63, "y": 43, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 47, "y": 69, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 91, "y": 29, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 69, "y": 55, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 77, "y": 57, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 45, "y": 89, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 99, "y": 39, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 63, "y": 77, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 77, "y": 75, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 95, "y": 61, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 63, "y": 99, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 99, "y": 97, "bonus": 2, "amount": 8, "html":
`<p></p>`
  },
  {"x": 99, "y": 99, "bonus": 2, "amount": 8, "html":
`<p></p>`
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
  const destAnimationDurMs = (new URL(window.location).searchParams.get('dur')) * 1000 || 20000;
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

  if (!(tlCommandId > 0)) {
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
            if (!+cellValue || DEBUG) {
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
        console.log(JSON.stringify({x: coln, y: rown, bonus: 2, amount: cellValue, html: ""}));
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
  localStorage.setItem(`x${GAME_NUM}`, document.body.scrollLeft);
  localStorage.setItem(`y${GAME_NUM}`, document.body.scrollTop);
}

function resumeScrol() {
  document.body.scrollLeft = +localStorage.getItem(`x${GAME_NUM}`);
  document.body.scrollTop = +localStorage.getItem(`y${GAME_NUM}`);
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

  // debugger;
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

