"use strict";

const CELL_SIZE_IN_REM = 3;
const MODAL_WIDTH_IN_CELLS = 5;
const MODAL_HEIGHT_IN_CELLS = 3;
const FOG_OF_WAR = 6;
const FOR_OPACITY_LEN = 6;

const DEBUG = false;

const GAME_NUM = 7;

const mapAsString = `
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\to\to\to\t1\t1\t1\t1\tx\t1\t3\t2\tx\t1\tx\t1\tx\t1\t2\t1\t1\t1\t2\t2\tx\t2\tx\t2\t2\t1\tx\t2\tx\t1\t2\t2\tx\t1\t2\t1\t2\t5\tx\t1\t2\t3\t1\t3\tx\t3\tx\t1\t3\t1\t5\t1\t3\t4\t5\t1\t3\t5\t4\t5\t3\t3\t3\t1\t1\t1\t1\t6\t4\t3\t3\t3\t3\t3\t3\t4\t1\t3\tx\t5\t1\t3\t4\t6\t4\t3\t3\t1\t4\t1\tx\t8\t1\t5\tx\t1\tx
x\to\to\to\tx\tx\tx\t1\tx\t1\tx\t2\tx\t3\tx\t2\tx\t3\tx\t1\tx\t1\tx\tx\tx\t1\tx\t3\tx\tx\tx\t3\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t3\t5\t4\t3\t3\tx\tx\tx\tx\tx\tx\tx\t4\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\t5\tx\t1\tx\t1\tx\t6\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t6\tx\t5\tx
x\to\to\to\tx\t8\tx\t1\t1\t1\tx\t2\t2\t1\t1\t1\t1\t2\tx\t2\tx\t2\t3\t2\t2\t3\t1\t5\t3\t3\t2\t2\t3\t1\t5\t2\t3\t2\t1\t1\t5\t1\tx\t2\t3\t3\t3\t3\tx\t1\t1\t2\tx\t3\t3\t3\t3\t1\t1\t3\t1\t3\t4\t4\tx\t1\tx\t1\tx\t1\tx\t3\tx\t8\tx\t3\t4\t5\tx\t3\tx\t4\tx\t8\tx\t4\tx\t4\tx\t4\tx\t3\t1\t6\tx\t4\t4\t1\t1\t4\tx
x\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t3\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t3\tx\t1\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\t3\tx\t3\tx\t1\tx\t5\tx\t3\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\t1\tx\t4\tx\t3\tx\t3\t1\t4\t3\t4\tx
x\t1\tx\t1\t1\t1\tx\t8\t1\t1\tx\t2\t1\t3\tx\t2\t2\t1\t2\t2\t1\t1\t1\t2\tx\t2\tx\t2\tx\t1\t3\t1\t2\t3\tx\t2\t1\t1\tx\t1\tx\t3\t2\t5\tx\t1\tx\t3\t2\t3\t5\t2\tx\t3\tx\t3\t1\t3\t3\t5\t4\t3\tx\t3\tx\t4\tx\t4\t4\t6\tx\t1\tx\t3\tx\t4\tx\t3\t3\t3\tx\t3\t1\t4\t3\t3\tx\t4\t1\t1\tx\t1\tx\t5\t3\t1\t4\t1\t1\t1\tx
x\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\t3\tx\t5\tx\tx\tx\t5\tx\t5\tx\t1\tx\t1\tx\t4\tx\tx\tx\t4\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\tx\tx\t4\tx\tx\tx\tx\tx\t3\tx\t4\tx\tx\tx\t1\t3\t5\t5\t1\tx
x\t1\tx\t1\t1\t1\t1\t1\tx\t1\t2\t2\t2\t2\t2\t1\tx\t1\tx\t1\tx\t3\t2\t3\t2\t2\t2\t2\t2\t2\t2\t8\tx\t3\tx\t2\t2\t1\t2\t3\tx\t1\t5\t3\t1\t4\t3\t3\tx\t3\tx\t3\tx\t1\t3\t4\t3\t3\t5\t4\t4\t4\tx\t1\tx\t5\t3\t4\t3\t3\t1\t3\tx\t3\tx\t3\t4\t1\t3\t3\t1\t3\tx\t3\t5\t4\t1\t3\t3\t1\t3\t3\tx\t1\t5\t3\t6\t1\t5\t6\tx
x\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t3\tx\t3\tx\t2\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t3\tx\t1\tx\tx\tx\tx\tx\t3\tx\t5\tx\tx\tx\tx\tx\t3\tx\t3\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx
x\t1\tx\t8\t1\t1\tx\t1\tx\t8\t1\t3\tx\t2\tx\t2\t1\t2\t1\t2\t3\t2\tx\t2\t3\t2\t5\t2\tx\t1\t2\t1\t2\t2\tx\t1\t2\t2\tx\t1\t2\t1\tx\t3\tx\t2\tx\t1\t4\t2\tx\t3\tx\t8\tx\t3\t4\t3\tx\t3\t1\t1\t3\t1\t3\t1\t4\t3\t1\t1\t1\t3\tx\t3\t5\t3\tx\t4\t3\t5\t1\t3\t3\t5\tx\t1\tx\t5\t3\t5\t1\t4\t3\t5\t5\t4\tx\t4\t1\t5\tx
x\t1\tx\tx\tx\t3\tx\t2\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t2\tx\tx\tx\t3\tx\tx\tx\t1\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\t3\t4\t3\t3\tx\tx\tx\t3\tx\tx\tx\t5\t3\t4\t3\t1\tx\t6\tx\tx\t1\t1\t1\t1\t5\t3\tx\tx\tx\tx\tx\t3\tx
x\t1\t1\t2\t2\t2\tx\t2\t1\t1\t2\t1\t1\t1\t2\t3\t1\t3\tx\t1\tx\t1\t3\t2\t1\t1\t1\t1\t1\t3\t5\t1\t1\t1\tx\t2\tx\t2\t2\t2\t2\t1\tx\t1\t4\t8\tx\t1\t3\t1\t5\t1\tx\t3\tx\t1\t3\t1\t1\t3\tx\t4\t3\t3\t3\t4\tx\t3\t4\t3\t3\t1\t1\t4\t1\t1\tx\t1\t3\t3\t1\t5\t1\t3\tx\t3\t1\t5\t1\t1\t3\t4\t1\t5\t3\t4\tx\t3\t3\t1\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t3\tx\t3\t2\t1\t2\t5\tx\t2\tx\t3\tx\t3\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\t3\t5\t4\t3\tx\t1\tx\t3\tx\t3\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\t1\t4\t4\t4\tx\t5\tx\tx\tx\t4\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\t3\t3\t1\t1\t4\tx\tx\tx\t5\t1\t3\t3\tx
x\t1\t2\t2\tx\t8\t1\t2\tx\t1\t2\t3\t2\t3\t2\t8\tx\t3\tx\t1\t2\t3\tx\t1\t2\t2\tx\t2\t1\t3\t3\t3\tx\t3\t2\t2\tx\t1\tx\t8\tx\t2\t2\t4\t2\t1\t4\t5\t5\t2\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t3\t3\t3\t1\t3\t3\t3\t3\t3\t4\t3\t3\tx\t3\tx\t1\t3\t3\tx\t3\tx\t3\t1\t5\tx\t4\tx\t5\tx\t4\tx\t6\t3\t1\t3\t4\t1\t1\t4\t1\tx
x\t3\tx\tx\tx\tx\tx\t1\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\t2\tx\t2\tx\t2\tx\tx\tx\t2\t3\t3\t3\t2\tx\t1\t2\t1\tx\t2\tx\t2\tx\t3\tx\tx\tx\tx\tx\tx\t1\t1\t3\t2\tx\t3\tx\t1\tx\tx\t3\t5\t4\t2\tx\t2\tx\tx\t3\t3\t5\t1\tx\t4\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t5\tx\t3\t3\t5\t4\t1\t4\tx\tx\tx\tx\tx\t6\t5\t3\t5\tx
x\t2\t1\t1\tx\t2\tx\t3\tx\t2\tx\t2\tx\t2\t1\t1\tx\t2\tx\t2\tx\t3\tx\t1\t2\t2\t3\t2\t2\t1\t1\t3\t1\t2\t2\t1\t2\t3\tx\t2\tx\t1\tx\t2\t1\t3\tx\t3\t5\t3\t1\t2\t2\t4\tx\t1\t1\t5\t1\t2\t5\t5\t5\t3\tx\t4\t3\t5\t3\t3\tx\t1\t1\t3\tx\t5\t5\t1\t4\t1\tx\t4\t4\t3\tx\t4\t1\t3\t6\t4\t3\t3\t6\t4\t6\t1\t6\t5\t5\t1\tx
x\t2\tx\tx\tx\t3\tx\t2\tx\t3\tx\tx\tx\t2\tx\tx\tx\t2\tx\t2\tx\t2\tx\tx\tx\t1\tx\tx\t1\t2\t1\t2\tx\tx\tx\tx\tx\t3\tx\t2\tx\tx\tx\t4\tx\tx\tx\tx\tx\t4\tx\tx\tx\t5\tx\tx\tx\tx\t2\t2\t1\t3\tx\t3\tx\t2\t1\t3\t4\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\t4\tx\tx\tx\t1\tx\t1\t1\t4\t3\t1\t5\t3\tx\t5\tx\tx\t3\t3\t1\tx\tx
x\t1\t2\t2\t2\t2\t3\t1\tx\t1\t2\t1\t2\t3\t2\t2\t1\t1\t2\t3\tx\t8\tx\t2\tx\t2\tx\t1\t2\t1\t1\t2\t2\t3\tx\t2\t1\t2\t3\t2\tx\t3\t1\t3\t2\t1\t1\t2\t2\t1\t5\t4\tx\t2\t2\t1\t1\t2\tx\t1\tx\t4\t3\t1\t2\t2\t4\t3\t4\t3\t1\t3\t3\t5\t4\t1\t3\t4\t5\t4\t1\t3\tx\t3\t3\t4\tx\t4\tx\t1\t3\t5\tx\t1\t1\t1\tx\t5\t1\t4\tx
x\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\t3\t1\t2\t2\tx\t2\tx\t2\tx\tx\tx\t1\tx\t1\tx\t3\tx\t2\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\t1\t1\t3\t3\tx\tx\tx\tx\tx\tx\tx\t5\tx\t3\t4\t3\t4\t3\t1\t4\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\t5\tx\t3\tx\tx\tx\t1\tx
x\t2\t1\t1\tx\t8\tx\t3\t2\t1\tx\t3\t5\t2\t2\t3\tx\t1\t3\t1\tx\t2\t1\t1\t2\t3\tx\t2\t1\t1\t1\t3\tx\t2\t1\t2\t2\t1\tx\t3\tx\t8\tx\t2\tx\t1\tx\t3\t3\t2\tx\t1\t3\t1\t1\t3\t1\t2\t1\t1\t2\t2\t2\t1\t1\t3\tx\t4\t3\t1\tx\t4\t3\t4\t1\t1\t3\t3\t3\t3\tx\t4\t5\t3\tx\t1\t3\t8\tx\t4\t5\t1\tx\t6\tx\t4\t3\t3\t3\t5\tx
x\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t3\t1\t1\t2\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\t2\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\t3\t1\t5\t2\tx\tx\tx\t3\tx\t1\tx\t1\tx\t1\t1\t1\t5\t1\t3\tx\tx\t4\tx\tx\tx\t3\tx\t1\tx\tx\tx\t5\tx\tx\tx\tx\tx\t1\tx\t5\tx\t4\tx
x\t3\t1\t1\tx\t2\tx\t3\tx\t2\tx\t2\t1\t5\t3\t3\t1\t1\tx\t3\tx\t2\t2\t1\tx\t8\tx\t3\tx\t2\tx\t2\t1\t3\t1\t3\tx\t2\t2\t2\tx\t4\t4\t2\tx\t1\t2\t2\tx\t8\t1\t4\t1\t3\tx\t4\tx\t3\t2\t1\t4\t3\t3\t1\tx\t1\tx\t3\tx\t3\tx\t5\tx\t5\tx\t1\tx\t3\t1\t1\tx\t3\t4\t3\tx\t1\tx\t1\tx\t5\tx\t3\t4\t3\tx\t1\tx\t1\tx\t1\tx
x\t2\tx\t3\tx\t3\tx\t2\tx\t2\tx\t1\t1\t2\t1\t2\tx\tx\tx\t2\tx\tx\tx\t3\tx\tx\tx\t2\tx\t3\tx\tx\tx\t2\tx\tx\tx\t2\t2\t3\t3\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\t3\t1\t3\t2\t2\tx\t2\tx\t2\tx\t3\tx\tx\t1\t1\t3\t3\t3\tx\tx\t4\tx\tx\tx\t3\tx\tx\tx\t3\tx\t1\tx\t4\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx
x\t3\tx\t8\tx\t2\t1\t3\t1\t1\t2\t2\t1\t2\t3\t1\tx\t5\t1\t2\t1\t2\tx\t1\t3\t3\tx\t1\t1\t5\tx\t2\tx\t2\tx\t2\tx\t5\t1\t3\t3\t3\tx\t3\tx\t4\t5\t3\tx\t2\tx\t3\tx\t1\tx\t3\t3\t2\tx\t4\tx\t2\tx\t4\tx\t8\tx\t1\t3\t3\t1\t3\t4\t1\t4\t3\t1\t3\t3\t3\t1\t3\t4\t3\t1\t4\tx\t3\t3\t1\t5\t1\t1\t3\t1\t1\t3\t1\t4\t5\tx
x\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\t3\t2\t2\t1\tx\t2\tx\tx\tx\t1\tx\t3\tx\t2\tx\t3\tx\t2\tx\t2\t2\t2\t3\t1\tx\t2\tx\t2\tx\tx\tx\t1\tx\t4\tx\t1\tx\t1\tx\t1\tx\t3\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\t3\t3\t1\t1\t3\tx\tx\t3\t1\t1\t3\tx\tx\tx\tx\t5\tx\t3\t4\t4\t6\t5\tx\tx\tx\tx\tx\t5\tx\t6\tx
x\t1\tx\t3\t1\t3\t3\t2\t2\t1\tx\t2\t2\t2\tx\t1\t2\t2\t2\t2\t1\t3\t2\t1\t1\t2\t1\t2\tx\t2\t3\t1\t2\t2\tx\t3\tx\t2\t1\t1\t1\t3\t3\t4\t1\t1\tx\t2\t1\t3\tx\t2\t1\t3\t3\t3\tx\t3\tx\t1\tx\t2\t3\t3\t5\t3\tx\t4\tx\t3\t3\t1\t3\t1\t1\t4\t1\t3\t3\t5\t3\t3\tx\t3\t1\t3\tx\t3\t3\t3\t4\t6\t4\t1\t4\t1\tx\t4\tx\t3\tx
x\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\t5\t3\t2\t1\t2\t3\t1\t5\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\t1\t1\t1\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\t1\t1\t3\tx\tx\t1\tx\t1\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t4\tx
x\t1\t2\t1\tx\t2\t2\t2\t1\t3\t1\t3\tx\t3\t2\t2\tx\t3\tx\t3\tx\t3\t3\t2\t2\t2\tx\t2\tx\t2\t3\t3\t3\t2\t3\t2\t2\t1\t1\t2\tx\t1\t5\t3\t4\t3\tx\t3\t5\t5\t2\t2\tx\t3\t3\t1\tx\t3\t3\t2\t1\t5\t1\t5\tx\t3\t3\t4\t3\t1\tx\t1\t1\t4\tx\t1\t1\t3\t1\t4\t4\t3\tx\t5\tx\t1\tx\t6\tx\t3\tx\t4\t1\t4\t4\t3\t3\t6\tx\t5\tx
x\t3\tx\t1\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\t2\tx\tx\tx\tx\tx\t4\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\t5\t2\t5\t5\tx\t5\tx\tx\tx\t2\tx\tx\t3\t5\t1\t1\t1\t1\t3\t4\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\t3\t3\t3\t3\tx\t1\tx\t4\tx\t1\tx\t1\tx\t3\tx\tx\tx\t4\tx\t1\tx\t5\tx
x\t3\tx\t2\t3\t2\tx\t2\t2\t2\tx\t2\t2\t2\tx\t3\tx\t2\tx\t2\tx\t1\tx\t3\t3\t3\tx\t1\t1\t2\tx\t3\t1\t2\tx\t3\t2\t2\tx\t2\t2\t1\t3\t2\t2\t2\t2\t5\t4\t4\tx\t2\tx\t2\t3\t5\t2\t2\t3\t3\t3\t1\t4\t1\t3\t1\t1\t3\t3\t1\t1\t3\tx\t3\t1\t1\t1\t3\tx\t3\t1\t1\t3\t4\tx\t1\tx\t3\t4\t5\tx\t1\tx\t6\t1\t5\tx\t4\t5\t4\tx
x\t2\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\t2\t5\t2\t5\t2\t2\tx\t3\tx\t5\tx\tx\tx\t3\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\t2\tx\t4\t3\t2\t3\t4\tx\tx\tx\t4\tx\tx\tx\tx\t2\t1\t2\t3\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t4\tx\tx\tx\t4\tx\t3\tx\tx\tx\tx\tx\tx\tx\t4\tx\t5\tx\tx\tx\t4\tx\tx\tx\t1\tx\tx\tx
x\t3\t3\t5\tx\t3\t1\t1\tx\t3\t1\t2\t3\t2\t3\t1\t3\t2\t3\t1\t2\t3\t2\t1\t3\t3\tx\t2\tx\t2\t1\t3\tx\t1\tx\t1\tx\t1\t1\t2\t5\t1\t1\t1\t1\t2\t2\t1\t3\t3\tx\t1\t5\t2\t1\t1\t2\t1\tx\t4\tx\t5\t3\t3\t3\t3\tx\t3\t1\t4\t4\t3\t3\t5\tx\t3\tx\t4\t1\t1\t3\t3\tx\t1\t1\t5\tx\t3\tx\t3\tx\t6\t1\t6\tx\t5\t4\t5\t1\t1\tx
x\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\t1\t2\t2\t2\t3\tx\tx\tx\tx\tx\tx\tx\tx\t2\t3\t1\t3\tx\tx\t2\tx\tx\tx\t2\tx\tx\t3\t1\t2\t1\tx\t5\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\t3\t3\t1\t4\t2\tx\tx\t1\tx\tx\tx\tx\tx\t4\tx\tx\tx\t1\tx\t3\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\t5\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t6\tx
x\t3\t1\t1\t1\t2\t3\t2\t2\t3\t2\t2\tx\t2\t2\t2\t1\t1\t3\t2\t3\t1\tx\t2\tx\t3\tx\t2\t3\t1\t2\t4\tx\t1\t3\t2\tx\t3\tx\t2\t2\t3\t5\t1\tx\t5\t4\t2\t2\t1\t2\t4\t3\t1\tx\t3\t2\t3\t2\t4\t3\t1\t1\t1\tx\t8\t3\t1\tx\t3\tx\t3\t1\t1\tx\t4\t4\t5\t4\t3\t3\t5\tx\t1\tx\t8\t5\t3\tx\t4\t5\t3\t5\t3\tx\t1\t1\t1\tx\t1\tx
x\tx\tx\t1\tx\tx\tx\tx\t3\t3\t2\t3\tx\t3\t1\t3\t2\t3\t2\t2\tx\tx\tx\t2\tx\t3\tx\tx\t1\t1\t3\tx\tx\t2\tx\t3\tx\tx\tx\t3\t5\t1\t5\t3\tx\tx\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\t1\t4\t2\t4\t1\tx\tx\t3\tx\tx\tx\t3\tx\tx\t3\t3\t1\tx\tx\t3\t1\t4\t4\t3\tx\t3\tx\t4\tx\tx\tx\tx\tx\tx\tx\t6\tx\t4\tx\tx\tx\tx\tx\tx\tx
x\t3\t1\t5\t2\t2\tx\t4\t1\t2\t1\t2\t3\t2\tx\t3\t5\t3\t2\t1\tx\t8\tx\t2\t2\t5\tx\t3\t1\t2\t2\t1\tx\t2\t2\t3\t3\t2\t2\t2\t5\t4\t2\t5\tx\t3\t2\t1\tx\t2\tx\t3\t3\t5\tx\t3\t3\t1\t3\t5\t3\t1\tx\t4\t4\t3\t3\t1\tx\t1\t3\t1\t4\t1\tx\t1\t1\t3\t3\t3\tx\t1\t3\t3\t3\t4\tx\t3\t4\t4\t3\t3\tx\t3\t1\t3\tx\t1\t3\t3\tx
x\t3\tx\t5\tx\tx\tx\t2\tx\t3\tx\tx\tx\t2\tx\t5\tx\tx\tx\tx\tx\t4\tx\t3\t2\t2\tx\t1\t1\t2\t1\t3\tx\t3\t2\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\t3\tx\t1\tx\tx\tx\tx\tx\t1\t3\t4\t3\t3\tx\t3\t1\t4\t3\t3\tx\tx\tx\tx\tx\t4\tx\t4\tx\tx\tx\t5\tx\t1\tx\tx\tx\t1\tx\t4\tx
x\t2\tx\t1\tx\t1\tx\t3\t2\t2\t3\t3\tx\t1\t2\t1\t2\t3\t1\t1\tx\t2\t2\t1\t3\t3\t2\t2\t3\t2\tx\t2\t2\t2\t2\t3\tx\t2\t3\t1\tx\t2\t1\t1\t5\t2\tx\t3\t3\t3\tx\t3\t3\t3\t3\t5\t1\t4\t4\t5\tx\t4\t3\t3\t1\t3\t3\t4\tx\t1\t3\t1\t3\t1\tx\t3\t4\t3\t1\t3\t3\t3\tx\t1\tx\t6\t1\t3\tx\t5\t3\t6\tx\t6\t1\t5\t1\t4\tx\t3\tx
x\tx\tx\t2\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t3\t2\t2\tx\t2\tx\t2\tx\tx\tx\t5\t2\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\t1\tx\t3\tx\t3\t3\t5\tx\tx\tx\t3\tx\t4\tx\tx\tx\t5\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx
x\t1\t2\t2\t1\t2\tx\t3\t2\t1\t1\t1\t5\t2\t1\t3\tx\t2\tx\t1\t3\t4\tx\t3\t3\t2\tx\t5\tx\t2\tx\t1\tx\t2\tx\t2\t3\t2\t2\t1\tx\t5\tx\t1\tx\t2\t2\t4\t5\t2\tx\t4\t1\t1\t1\t5\tx\t1\t3\t3\t5\t1\t3\t1\t3\t1\tx\t4\t3\t1\t1\t3\tx\t3\t3\t4\t3\t3\tx\t1\t4\t6\tx\t1\t5\t1\t1\t4\tx\t1\t5\t1\tx\t6\t1\t4\tx\t3\tx\t1\tx
x\tx\tx\tx\tx\t3\tx\tx\tx\t3\tx\t2\t1\t1\t3\t4\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\t5\tx\t1\t1\t3\t3\t2\tx\tx\tx\t3\tx\t4\tx\t4\tx\t2\tx\t4\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\t6\tx\tx\tx\t4\tx\tx\tx\t3\tx\tx\tx\t3\tx
x\t8\t3\t5\t3\t3\tx\t2\t3\t3\t2\t5\t2\t1\t5\t4\tx\t3\tx\t3\tx\t2\t1\t4\t2\t2\tx\t5\tx\t2\t3\t3\t5\t3\t1\t1\t2\t1\tx\t1\t1\t1\t3\t2\t1\t4\tx\t1\tx\t1\t1\t5\tx\t1\t1\t1\t1\t3\tx\t1\t4\t5\tx\t4\t5\t3\t4\t1\t3\t1\tx\t1\t4\t1\tx\t3\tx\t3\tx\t1\t1\t5\tx\t4\t1\t5\tx\t4\tx\t3\t6\t4\t3\t3\t3\t1\t1\t3\tx\t3\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t3\t1\t2\t4\tx\t2\tx\t1\tx\tx\tx\t2\tx\t3\tx\t5\tx\tx\tx\t2\t2\t3\t2\t1\tx\tx\tx\tx\tx\t4\tx\tx\tx\t1\tx\t1\tx\t4\tx\t3\tx\t4\tx\t3\tx\tx\tx\t4\tx\t3\tx\tx\t3\t5\t1\tx\tx\t1\tx\t4\tx\t3\tx\t3\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\t6\tx\t4\tx\tx\tx\tx\tx\t1\tx\tx\tx\t5\tx
x\t3\t6\t1\tx\t8\tx\t2\t3\t3\t1\t2\t2\t1\t1\t1\t5\t1\t3\t3\t3\t2\t1\t3\tx\t3\t1\t2\tx\t5\t2\t1\t3\t1\t2\t2\t2\t1\t1\t4\tx\t3\tx\t4\t2\t4\tx\t1\tx\t8\tx\t3\t5\t1\t1\t3\t1\t1\tx\t1\tx\t3\tx\t1\t4\t3\t3\t5\tx\t1\tx\t3\tx\t1\t4\t1\tx\t1\t6\t3\tx\t4\tx\t1\t1\t6\tx\t4\tx\t4\tx\t3\t5\t5\tx\t6\t3\t1\tx\t3\tx
x\t3\tx\t3\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\t1\t3\t3\t4\tx\t1\tx\t1\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\t3\t4\t4\t3\tx\t5\tx\tx\tx\tx\tx\tx\t1\t4\t3\t3\tx\t1\tx\tx\tx\t3\tx\t3\tx\t5\tx\t5\tx\t5\tx\t6\tx\tx\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\t1\tx
x\t4\tx\t1\tx\t3\t3\t3\tx\t4\tx\t1\t1\t5\tx\t2\t3\t3\t1\t3\t1\t2\tx\t1\tx\t5\tx\t1\tx\t1\tx\t3\t1\t2\t1\t3\tx\t1\t4\t1\t3\t3\tx\t1\tx\t1\tx\t8\tx\t4\tx\t3\t1\t3\t3\t3\tx\t3\t1\t1\t1\t3\tx\t3\t3\t3\t3\t4\tx\t4\tx\t5\t3\t4\tx\t4\t1\t3\tx\t5\tx\t1\t3\t6\t3\t4\t4\t1\tx\t1\t6\t6\t1\t1\tx\t3\t3\t1\t5\t4\tx
x\t4\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t3\tx\tx\t5\t5\t1\t3\tx\tx\tx\tx\tx\t2\tx\tx\tx\t3\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\t1\tx\t3\tx\tx\tx\t4\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\t3\tx\tx\tx\t4\tx\t3\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t4\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\t3\tx
x\t4\tx\t3\tx\t1\t3\t3\t4\t3\t3\t1\t4\t3\tx\t3\t3\t1\tx\t1\tx\t1\t4\t1\tx\t1\t5\t2\t1\t4\t2\t1\tx\t2\t4\t1\tx\t3\t3\t1\t3\t3\tx\t1\t3\t3\t1\t1\t3\t4\t1\t1\tx\t3\t3\t1\t5\t4\t1\t5\tx\t4\t1\t1\tx\t1\tx\t5\t5\t3\tx\t1\tx\t3\tx\t3\tx\t1\t1\t3\tx\t3\tx\t3\t6\t5\tx\t6\tx\t3\tx\t1\t5\t4\t1\t4\t1\t3\tx\t1\tx
x\t4\tx\t1\tx\tx\tx\t3\tx\tx\tx\t4\tx\t1\tx\tx\tx\t3\tx\tx\tx\t4\tx\t3\tx\t2\tx\tx\tx\t1\tx\t3\tx\t2\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\t1\t1\t1\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\t6\tx\tx\tx\t3\tx\tx\tx\tx\tx\t4\t1\t1\t4\t5\tx\tx\tx\t5\t1\t4\t6\tx\tx
x\t4\tx\t8\tx\t3\tx\t4\tx\t1\t3\t3\tx\t5\tx\t1\tx\t1\t5\t1\t4\t3\tx\t4\tx\t1\tx\t5\t3\t2\tx\t4\tx\t3\t3\t8\tx\t6\tx\t3\tx\t6\t1\t1\t3\t1\tx\t3\t1\t5\t3\t3\tx\t5\tx\t1\t3\t3\t3\t1\tx\t3\t1\t1\t1\t4\t5\t4\t3\t3\tx\t3\tx\t5\t4\t5\t1\t5\t4\t1\tx\t3\t1\t4\tx\t4\t4\t3\t4\t3\t4\t5\t4\t5\t3\t3\t6\t5\t1\t6\tx
x\t3\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t1\tx\t5\tx\t3\tx\tx\tx\tx\tx\t1\t2\t2\t3\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t1\tx\t5\tx\t4\tx\tx\tx\t3\t1\t4\t3\tx\tx\t3\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\t3\tx\t7\tx\t4\tx\tx\tx\tx\t5\t6\t6\t5\tx\t3\tx\tx\t1\t1\t5\t4\tx
x\t5\t3\t3\t3\t3\t4\t3\tx\t3\t1\t3\tx\t3\tx\t3\t1\t1\tx\t1\tx\t5\t3\t1\t1\t2\t1\t2\t2\t3\t3\t4\t5\t4\tx\t1\tx\t4\tx\t1\tx\t3\t5\t3\tx\t5\t5\t3\t1\t1\tx\t4\tx\t3\tx\t3\tx\t1\tx\t3\tx\t4\t5\t3\t5\t1\t1\t3\tx\t1\t3\t5\tx\t4\tx\t5\t7\t1\t6\t6\t5\t1\tx\t3\tx\t6\t3\t1\t1\t1\tx\t3\tx\t1\t4\t5\t4\t4\t1\t1\tx
x\tx\tx\t3\tx\tx\tx\t1\tx\t4\tx\t3\t1\t3\t3\t4\tx\tx\tx\t1\tx\tx\tx\t3\t1\t5\t1\tx\tx\t4\tx\tx\tx\tx\tx\t5\tx\t3\tx\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\t3\tx\t5\tx\t1\tx\tx\tx\t6\tx\tx\tx\tx\tx\t1\tx\t3\tx\t1\tx\t1\tx\t3\tx\t5\tx\tx\tx\t1\tx\tx\tx\t3\tx\t5\tx\tx\tx\t4\tx\t1\tx\t5\tx\tx\tx\tx\tx\t4\tx
x\t3\t1\t3\t3\t4\tx\t3\t1\t1\tx\t1\t5\t3\t3\t5\t4\t4\tx\t1\t3\t1\tx\t3\t5\t1\t5\t5\t3\t5\t3\t3\tx\t8\tx\t5\t1\t3\t3\t3\tx\t3\t3\t5\t5\t4\tx\t1\t1\t1\t6\t1\t5\t3\t4\t3\t3\t1\tx\t4\tx\t1\t4\t5\t5\t3\tx\t1\tx\t4\tx\t4\t3\t3\tx\t5\t5\t8\tx\t3\t5\t1\tx\t1\t1\t3\tx\t5\t5\t5\tx\t1\tx\t5\t1\t5\tx\t6\tx\t4\tx
x\tx\tx\tx\tx\t1\tx\t5\tx\tx\tx\t3\t3\t3\t1\tx\tx\tx\tx\tx\tx\t4\tx\t3\t3\t1\t3\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\t1\t5\t3\t5\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\t3\tx\t4\tx\t5\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t6\tx\tx\tx\t4\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\t4\tx
x\t8\t1\t3\tx\t1\tx\t3\t5\t5\tx\t3\t3\t1\t1\t3\t1\t1\t1\t3\tx\t4\tx\t3\tx\t3\t3\t4\tx\t3\t1\t4\tx\t3\tx\t1\t3\t1\t3\t5\t4\t1\t3\t4\tx\t3\t1\t3\t6\t1\t3\t4\t5\t1\t3\t1\t4\t5\tx\t4\t1\t3\tx\t4\tx\t5\tx\t4\tx\t5\tx\t3\tx\t4\tx\t3\t4\t6\tx\t1\tx\t3\t4\t1\t1\t3\tx\t1\tx\t5\t4\t3\t1\t6\tx\t1\tx\t6\t3\t4\tx
x\tx\tx\t6\tx\tx\tx\t3\tx\t4\tx\t3\tx\t3\tx\t3\tx\t3\tx\tx\tx\t1\tx\t4\tx\tx\tx\tx\tx\t1\tx\t4\tx\t5\tx\t3\tx\tx\tx\t5\t1\t6\t3\t3\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\t5\t4\t3\tx\tx\tx\t3\tx\t5\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t3\tx\t7\tx\t3\tx\t1\tx
x\t3\t3\t1\tx\t4\tx\t4\tx\t1\t3\t3\t1\t3\t3\t3\tx\t4\tx\t4\tx\t3\t4\t3\t1\t3\t1\t4\tx\t4\tx\t4\tx\t5\tx\t4\tx\t5\t1\t1\t1\t4\t1\t5\t1\t4\t3\t4\tx\t3\tx\t1\t3\t1\tx\t5\t3\t4\t1\t3\t3\t1\t3\t5\t1\t3\t6\t3\tx\t1\t1\t3\t3\t1\t1\t4\tx\t1\tx\t3\t5\t7\t5\t1\t3\t6\tx\t3\t1\t1\tx\t1\t5\t4\t5\t6\tx\t5\tx\t1\tx
x\t3\tx\t4\tx\t3\tx\tx\tx\t4\tx\tx\t3\t4\t4\t3\tx\tx\tx\t3\tx\t4\tx\tx\tx\t3\t3\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\t5\t5\t5\t1\t1\tx\tx\tx\tx\tx\t1\t3\t4\t4\t5\t1\tx\t3\t1\t4\tx\t5\t5\t6\t1\t1\tx\t5\tx\t3\tx\t5\t1\t4\t4\t3\tx\t3\tx\t1\tx\tx\tx\t5\tx\tx\tx\t3\tx\tx\tx\t3\tx\t4\tx\tx\tx\tx\tx\t3\tx
x\t4\tx\t5\tx\t3\t3\t5\tx\t4\tx\t1\t3\t3\t3\t1\tx\t3\t3\t4\tx\t4\tx\t1\t3\t5\t5\t1\t5\t3\tx\t3\t3\t1\tx\t1\t1\t4\t1\t1\t3\t1\t5\t3\t1\t6\t5\t5\t4\t3\t1\t3\t4\t5\t3\t5\tx\t3\t6\t3\tx\t3\t1\t6\t5\t5\t3\t3\t4\t3\tx\t4\t4\t4\t1\t4\tx\t1\t4\t1\tx\t4\t6\t4\tx\t3\t7\t3\t3\t3\t4\t6\tx\t1\tx\t5\t3\t1\t1\t1\tx
x\t1\tx\tx\tx\t1\t3\t3\t3\tx\tx\t3\t4\t1\t1\t5\tx\t3\tx\tx\tx\t1\tx\tx\tx\t3\tx\t3\tx\tx\tx\t5\tx\t5\tx\t3\tx\t1\tx\t6\t3\t5\t5\t3\t1\t4\tx\tx\tx\t3\t1\t6\t3\t1\t5\t1\tx\t1\tx\tx\tx\t5\tx\t3\tx\tx\tx\t6\tx\tx\tx\t1\t3\t3\t4\t4\tx\t4\tx\t3\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t7\tx
x\t4\t4\t1\t4\t3\t1\t3\t3\t3\t3\t3\tx\t4\tx\t3\tx\t3\t4\t4\t1\t4\tx\t5\t1\t1\t4\t3\tx\t4\t3\t4\tx\t1\t4\t6\tx\t3\tx\t3\t4\t1\tx\t1\tx\t4\tx\t5\t3\t1\t3\t1\t4\t1\t5\t1\tx\t4\tx\t6\tx\t1\tx\t1\tx\t1\t5\t6\tx\t6\tx\t4\tx\t6\t4\t4\tx\t3\tx\t4\tx\t1\t3\t5\tx\t3\t3\t8\tx\t5\tx\t7\t5\t3\tx\t1\tx\t3\t3\t1\tx
x\t1\tx\t3\t3\t4\t1\t3\t4\t1\t4\t4\t3\t1\tx\t3\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\t5\tx\tx\tx\t3\tx\t3\tx\t4\tx\tx\tx\t1\tx\t6\tx\t5\tx\t5\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\tx\t1\tx\tx\tx\t1\tx\t7\tx\t5\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t4\tx
x\t4\tx\t1\tx\t1\t3\t3\t4\t3\t5\t1\t3\t5\t3\t1\t5\t4\t4\t3\t1\t1\tx\t4\t3\t1\t1\t4\t3\t5\t3\t1\tx\t1\t5\t4\t6\t5\t4\t1\tx\t6\tx\t1\t1\t4\tx\t3\tx\t1\tx\t5\t4\t1\t5\t1\t4\t4\t3\t4\t3\t1\t6\t6\t5\t3\t4\t3\t3\t3\tx\t5\t3\t6\tx\t5\tx\t1\t1\t7\tx\t5\tx\t3\tx\t1\tx\t6\t1\t7\t1\t3\t6\t1\tx\t3\tx\t7\tx\t5\tx
x\tx\tx\t3\tx\tx\tx\tx\tx\t1\t1\t4\t1\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\t3\tx\t4\tx\t3\tx\t3\tx\t4\t4\t3\t1\t6\t3\tx\tx\t3\tx\t5\tx\tx\tx\tx\tx\t5\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\t1\tx\t1\tx\t7\tx\tx\tx\t3\tx\tx\tx\tx\tx\t4\tx\t3\tx\t3\tx
x\t4\t3\t4\tx\t3\t3\t3\tx\t4\t3\t3\t3\t4\tx\t3\t3\t3\tx\t3\tx\t4\tx\t5\tx\t1\tx\t3\tx\t5\tx\t4\tx\t1\t3\t1\t5\t1\t3\t1\t1\t1\tx\t4\tx\t6\t5\t3\tx\t5\t3\t4\tx\t5\tx\t4\tx\t6\t1\t5\t4\t5\tx\t5\t3\t5\tx\t1\t6\t4\t3\t3\t5\t3\t1\t3\tx\t3\t4\t8\tx\t1\tx\t3\t3\t4\t3\t5\t3\t3\t5\t7\t7\t3\t5\t1\tx\t1\tx\t4\tx
x\t3\t3\t3\tx\t1\tx\tx\tx\t4\t1\t1\t1\t3\tx\tx\tx\tx\tx\t4\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t4\tx\tx\t3\t1\t5\t4\t3\tx\tx\t4\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t6\tx\tx\tx\t6\t5\t7\t3\t5\tx
x\t1\t1\t1\tx\t4\tx\t8\tx\t5\t5\t4\tx\t1\t3\t1\tx\t1\tx\t1\t3\t3\t3\t3\t5\t1\tx\t3\tx\t1\t3\t5\tx\t4\t1\t3\tx\t1\tx\t5\t1\t1\t3\t5\t1\t3\t5\t4\tx\t1\tx\t8\tx\t5\t5\t1\t1\t1\t4\t5\t3\t3\tx\t3\t3\t3\t3\t3\t1\t1\t3\t5\tx\t3\t3\t5\tx\t4\t3\t1\tx\t1\tx\t7\tx\t1\tx\t7\tx\t5\tx\t1\tx\t3\t3\t1\t3\t7\t5\t3\tx
x\t1\t1\t1\tx\t3\tx\t5\tx\tx\tx\t3\tx\tx\tx\t4\tx\t3\tx\tx\tx\tx\tx\t4\tx\tx\tx\t4\tx\t4\tx\tx\tx\t4\tx\tx\tx\t4\tx\tx\tx\t3\tx\t5\t3\t4\tx\tx\tx\t5\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\t1\t3\t4\t1\tx\t3\tx\tx\tx\tx\tx\t4\tx\t6\tx\t3\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\t6\t1\t5\t6\tx
x\t1\t4\t1\t1\t4\tx\t4\tx\t4\t4\t1\t1\t4\tx\t3\t3\t3\t3\t4\tx\t3\t4\t5\t3\t1\tx\t3\t3\t3\t1\t3\t3\t1\tx\t3\tx\t3\tx\t3\t5\t6\tx\t1\t1\t5\t6\t5\tx\t3\tx\t3\t1\t3\tx\t3\t1\t6\tx\t1\t6\t1\tx\t6\t4\t4\t4\t5\t4\t3\t1\t1\t1\t4\t3\t4\tx\t3\t3\t3\t1\t5\tx\t4\tx\t7\t3\t3\t7\t4\t7\t3\tx\t6\t6\t3\tx\t4\tx\t6\tx
x\tx\tx\t3\tx\tx\tx\t4\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\t1\tx\tx\tx\tx\tx\t3\t1\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\t3\t3\t1\t4\t1\tx\tx\t5\tx\tx\tx\t3\t6\t4\t1\t4\tx\t6\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t4\tx\t4\tx\tx\tx\tx\tx\t1\tx
x\t3\t4\t3\tx\t3\t5\t3\tx\t4\tx\t3\t3\t4\tx\t1\t4\t3\t3\t4\t1\t3\tx\t3\t1\t1\t3\t3\t6\t3\t5\t3\t4\t1\t6\t4\t5\t6\t4\t6\t5\t3\tx\t3\t1\t4\tx\t4\t4\t1\t1\t5\t6\t1\t1\t5\t1\t3\t1\t1\t4\t1\tx\t3\t1\t5\tx\t1\tx\t1\t3\t5\tx\t5\t1\t6\t7\t3\t3\t3\t4\t1\t3\t1\t3\t3\tx\t1\tx\t1\t7\t1\tx\t3\t5\t1\t3\t1\t3\t3\tx
x\t5\tx\t1\tx\t5\t5\t1\tx\t5\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t4\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\t1\t3\t1\t3\tx\tx\tx\t6\tx\t3\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\t5\t6\t4\t5\t1\tx\tx\tx\tx\tx\tx\t1\tx\t4\tx\tx\tx\tx\tx\t5\tx\tx\t1\t1\t4\tx\tx\tx\tx\t7\tx\t3\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\t5\tx
x\t5\tx\t1\tx\t1\t4\t3\t6\t5\tx\t1\t1\t1\tx\t7\tx\t1\t1\t1\tx\t1\tx\t3\t5\t3\tx\t5\t4\t5\tx\t4\t1\t3\t5\t5\tx\t1\t3\t3\tx\t3\tx\t3\t5\t4\tx\t8\tx\t7\t5\t3\t3\t6\tx\t7\t3\t5\t6\t6\t3\t3\tx\t3\t5\t1\tx\t3\t3\t3\t1\t7\tx\t8\tx\t1\t1\t5\t5\t6\t3\t1\t6\t1\tx\t5\tx\t3\t1\t1\tx\t1\tx\t6\t3\t4\t5\t4\t1\t3\tx
x\t4\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\t4\tx\tx\tx\t3\t1\t3\t1\t5\tx\tx\tx\tx\tx\t4\tx\t5\tx\tx\tx\t3\tx\t1\tx\tx\tx\tx\tx\t1\t5\t3\t3\tx\tx\tx\tx\t1\t1\t5\t1\tx\tx\t1\tx\t5\tx\t7\tx\tx\tx\tx\t1\t6\t7\tx\tx\tx\tx\t6\tx\t3\tx\tx\tx\t3\tx\t3\tx\t1\tx\tx\tx\tx\tx
x\t3\t6\t5\tx\t6\t3\t6\t6\t3\tx\t1\tx\t3\tx\t7\t4\t3\t3\t1\tx\t4\t1\t3\t7\t6\t3\t4\tx\t6\t4\t1\tx\t1\t1\t3\t3\t5\t5\t1\tx\t5\t1\t4\tx\t5\t6\t6\tx\t1\t3\t1\tx\t1\tx\t4\t3\t5\t4\t6\tx\t5\t1\t3\t3\t1\t6\t1\t1\t3\tx\t4\t3\t1\tx\t8\tx\t1\t5\t7\t6\t4\t3\t1\t3\t3\t1\t3\tx\t1\tx\t1\tx\t5\tx\t3\t4\t3\t5\t1\tx
x\t4\t1\t1\tx\t4\tx\tx\tx\t1\tx\t6\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\t3\tx\tx\tx\t3\tx\tx\tx\t4\tx\tx\tx\t3\tx\t3\tx\t3\tx\t3\tx\tx\tx\t3\tx\tx\t5\t1\t4\t1\tx\tx\tx\t3\t3\t1\t5\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\t5\tx\t3\tx\tx\tx\tx\tx\t7\tx\t1\tx\t6\tx\t3\tx\tx\tx\tx\tx\tx\tx\t7\tx
x\t5\t5\t1\t3\t1\t4\t1\tx\t1\t5\t5\tx\t8\t6\t3\t3\t5\t1\t5\t1\t5\t7\t3\t3\t5\tx\t4\t5\t1\tx\t3\t1\t5\t1\t3\tx\t5\t4\t1\tx\t5\t3\t3\t4\t5\tx\t5\tx\t1\tx\t3\t4\t1\tx\t5\t1\t7\tx\t5\t1\t1\tx\t1\tx\t5\t3\t1\t1\t7\tx\t1\tx\t6\t1\t1\tx\t3\tx\t5\t5\t1\t6\t1\tx\t5\tx\t5\t6\t1\tx\t1\tx\t1\tx\t1\tx\t5\tx\t1\tx
x\t3\t5\t4\tx\t3\tx\t4\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t4\tx\t5\tx\tx\tx\t7\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\t3\tx\t3\tx\t3\tx\tx\tx\tx\tx\t4\tx\t1\t1\t6\t1\tx\tx\t5\tx\t5\tx\t7\tx\t3\tx
x\t1\t4\t3\t1\t5\tx\t1\tx\t6\tx\t5\t1\t3\t3\t7\tx\t3\t1\t6\t1\t3\tx\t1\tx\t6\tx\t8\tx\t3\t4\t1\t1\t4\tx\t1\t4\t3\t1\t6\t5\t6\t1\t3\t3\t3\t6\t5\tx\t1\t5\t6\tx\t7\tx\t1\t3\t6\t5\t7\tx\t1\t3\t6\t1\t1\tx\t5\tx\t3\t4\t4\t1\t5\t5\t7\tx\t3\t6\t3\tx\t5\tx\t6\t1\t1\tx\t1\t3\t5\t6\t5\t5\t3\t1\t5\t7\t3\tx\t1\tx
x\t4\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t3\t6\t1\t1\t3\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t3\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t5\tx\t1\tx\tx\tx\t5\tx\t5\tx\tx\tx\t4\tx\t4\tx\t1\tx\tx\tx\tx\tx\t5\tx\tx\tx\t5\tx\tx\tx\tx\tx\t5\t1\t6\t3\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx
x\t1\tx\t3\t4\t3\tx\t1\tx\t1\t3\t1\t5\t7\tx\t3\t3\t5\t6\t6\t3\t5\t3\t3\t1\t3\tx\t4\t1\t1\tx\t3\tx\t4\t4\t4\t1\t5\t6\t3\t1\t1\tx\t6\tx\t5\t6\t4\t7\t6\t4\t4\t3\t3\t3\t5\tx\t4\t5\t5\tx\t5\tx\t6\tx\t1\t5\t5\tx\t1\t5\t7\t3\t4\t4\t5\t5\t4\t5\t1\t7\t1\t1\t3\t5\t1\t3\t1\t1\t7\t6\t3\tx\t1\tx\t1\t7\t1\t3\t1\tx
x\t4\tx\tx\tx\t1\tx\t5\tx\tx\tx\tx\tx\t1\tx\tx\tx\t5\t1\t4\t7\t5\tx\t6\tx\t3\tx\tx\tx\t3\tx\t1\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\t3\tx\t7\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\t7\tx\tx\t1\t1\t3\t3\t3\tx\tx\t7\tx\tx\t7\t7\t3\t1\tx\t5\tx\t3\t1\t5\t3\t1\tx\t5\tx\tx\tx\tx\tx\t7\tx
x\t3\t3\t1\tx\t1\t5\t5\t3\t1\tx\t5\t3\t1\t5\t5\t1\t1\tx\t3\t7\t6\tx\t6\tx\t5\tx\t3\t1\t3\t5\t1\t3\t5\t1\t3\t3\t1\tx\t4\tx\t6\t3\t3\tx\t1\t1\t1\tx\t3\t3\t3\tx\t1\tx\t3\tx\t6\t1\t5\tx\t1\t5\t5\t1\t4\tx\t1\t4\t6\t5\t3\t5\t3\t1\t3\tx\t1\t1\t5\t6\t3\t1\t3\tx\t5\t1\t1\t1\t1\tx\t1\tx\t5\t6\t3\tx\t5\t3\t1\tx
x\t1\tx\t1\tx\t6\tx\tx\tx\t4\tx\tx\tx\tx\tx\t1\tx\t5\tx\t5\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\t3\tx\t6\tx\tx\tx\tx\tx\t3\tx\t3\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t6\tx\tx\tx\t3\tx\t7\tx\tx\tx\tx\tx\tx\tx\t5\t4\t4\t5\t1\t3\t3\tx\tx\tx\tx\t5\t1\t6\t4\tx\t1\t3\t7\t6\t1\tx\t5\tx\t3\t1\t4\tx\tx\tx\tx\tx
x\t5\tx\t5\t5\t1\tx\t5\tx\t8\tx\t1\t1\t7\t5\t3\tx\t1\t3\t1\tx\t6\t6\t5\t3\t3\tx\t5\t5\t1\tx\t1\tx\t1\tx\t4\t1\t4\tx\t3\t6\t4\tx\t6\t4\t7\t1\t7\tx\t4\tx\t3\tx\t3\t5\t5\t1\t7\t1\t1\t1\t4\t6\t5\t1\t5\tx\t5\t3\t3\t3\t5\t3\t5\t1\t4\t5\t3\t1\t3\t3\t1\tx\t1\t5\t4\t1\t1\t1\t5\tx\t3\tx\t5\t3\t4\tx\t8\t7\t1\tx
x\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\t1\t4\t5\t4\t5\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\t1\tx\t6\tx\tx\tx\t6\tx\tx\tx\tx\tx\t3\tx\t6\tx\tx\tx\tx\tx\t3\t4\t1\t1\t4\tx\tx\tx\t3\tx\t3\tx\tx\tx\t5\t3\t5\t4\t1\tx\t1\tx\t7\t1\t1\tx\tx\tx\t4\tx
x\t3\t1\t4\tx\t7\t5\t4\t3\t5\tx\t1\t6\t1\t5\t1\tx\t4\tx\t1\t5\t1\t1\t5\tx\t1\tx\t1\t5\t3\t4\t5\t6\t6\tx\t3\t6\t5\tx\t3\t1\t1\t6\t5\t3\t5\t7\t3\tx\t8\tx\t1\t1\t1\t3\t3\tx\t3\tx\t3\tx\t1\tx\t5\t6\t5\t5\t4\tx\t1\t5\t5\t3\t5\t3\t1\t7\t6\t3\t6\tx\t1\tx\t3\t3\t6\t1\t3\tx\t5\t1\t1\t3\t3\t1\t1\tx\t1\t1\t1\tx
x\t5\tx\tx\tx\t7\tx\tx\tx\t7\tx\t3\tx\t1\tx\t7\tx\t6\tx\tx\tx\tx\tx\t4\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\tx\t5\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t5\tx\t5\t6\t1\t1\t3\tx\t1\tx\t5\t3\t1\t3\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\t1\t1\t3\t7\t5\tx\t1\tx\tx\tx
x\t5\t3\t3\tx\t1\tx\t7\t5\t3\t1\t1\tx\t1\tx\t1\tx\t5\t1\t1\tx\t3\t4\t3\t6\t4\tx\t4\t3\t1\t3\t1\t4\t6\t3\t3\t5\t1\tx\t3\t1\t4\tx\t1\t4\t4\tx\t1\tx\t3\t5\t3\t1\t4\t1\t5\tx\t5\tx\t1\t1\t6\t3\t3\t5\t5\t3\t4\t4\t6\tx\t3\t1\t3\t3\t3\tx\t1\t1\t3\t6\t6\tx\t1\t6\t1\t1\t7\tx\t3\tx\t7\t6\t4\t4\t1\t7\t5\t7\t7\tx
x\t5\tx\t1\tx\t7\tx\t5\t3\t3\t6\t4\tx\tx\tx\tx\tx\t1\tx\t5\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\t4\t4\t1\t6\t3\tx\tx\t4\tx\tx\tx\t5\tx\tx\tx\t7\tx\t4\tx\tx\tx\t3\tx\t5\t7\t1\t6\tx\tx\tx\tx\t1\t5\t3\t6\tx\tx\t5\tx\t3\tx\t6\tx\tx\tx\t4\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t5\tx\tx\tx\t1\tx\tx\tx\t5\tx\tx\tx
x\t5\tx\t6\tx\t5\tx\t1\t5\t1\t7\t3\t3\t1\t1\t1\tx\t4\tx\t1\t1\t3\t1\t7\t6\t5\t3\t1\tx\t1\tx\t3\t3\t5\t6\t5\t3\t5\t6\t1\t5\t5\tx\t1\tx\t7\t5\t6\tx\t3\tx\t7\tx\t3\t1\t7\t3\t5\t7\t5\tx\t5\t3\t3\t1\t3\t7\t3\tx\t6\tx\t3\tx\t1\t1\t3\t1\t3\t3\t1\tx\t1\tx\t1\t4\t1\t7\t4\tx\t7\tx\t4\t7\t1\tx\t3\tx\t7\t7\t7\tx
x\t1\tx\t1\tx\t1\tx\t5\t5\t5\t3\t3\tx\tx\tx\t4\t6\t4\t5\t4\t6\tx\tx\t1\tx\t1\tx\t1\tx\t4\tx\t6\t5\t5\t4\t1\t5\tx\tx\tx\tx\t1\tx\t3\tx\t4\tx\tx\tx\t5\tx\t1\tx\t3\tx\t4\t1\t1\t5\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\tx\t7\tx\t1\tx\t4\tx\tx\tx\t3\t1\t3\t7\t3\tx\tx\tx\t1\tx\t7\tx\t7\tx\t4\tx\tx\tx
x\t1\tx\t1\tx\t3\t3\t3\t3\t1\t7\t1\tx\t7\tx\t5\t3\t4\t4\t7\t5\t1\t1\t1\tx\t1\t5\t3\t5\t3\t3\t1\tx\t3\tx\t1\t4\t1\tx\t3\t1\t5\tx\t3\t3\t3\t1\t5\t4\t7\t1\t1\t5\t1\tx\t4\t5\t3\t4\t3\t5\t7\t6\t5\tx\t1\t1\t5\t6\t1\tx\t4\t4\t7\tx\t1\tx\t5\t3\t7\t7\t1\tx\t1\t5\t1\t6\t1\t5\t1\t6\t1\tx\t7\tx\t1\t5\t7\t1\t1\tx
x\t1\tx\t3\tx\t3\t6\t1\tx\tx\tx\t1\t5\t4\t7\t1\t6\t3\t1\t1\t1\tx\tx\tx\tx\tx\t3\t5\t4\t1\t1\t3\tx\t3\tx\tx\tx\t6\tx\tx\tx\t6\tx\tx\tx\t1\tx\t6\t4\t6\t3\t1\t1\t1\tx\t1\t7\t1\t3\t6\tx\tx\tx\t5\tx\tx\tx\tx\tx\t6\tx\t3\tx\tx\tx\t3\tx\t5\t1\t7\t4\t5\tx\t4\tx\tx\tx\t3\tx\tx\tx\t5\tx\t1\tx\tx\tx\t7\tx\t3\tx
x\t5\tx\t5\t1\t3\t3\t3\tx\t5\tx\t7\t1\t5\t7\t1\t5\t5\t1\t1\t3\t3\tx\t4\t3\t1\t7\t6\t3\t1\t6\t1\t4\t4\t1\t5\tx\t1\tx\t8\tx\t3\t6\t5\t3\t7\t3\t6\t4\t1\t3\t3\t6\t3\t5\t6\tx\t7\tx\t5\tx\t3\t5\t3\tx\t7\tx\t5\t7\t1\t7\t1\tx\t1\t1\t5\tx\t6\t7\t3\t7\t5\t5\t5\tx\t7\tx\t1\tx\t3\t3\t6\tx\t6\t7\t5\tx\t3\tx\t3\tx
x\tx\tx\tx\tx\t6\t1\t7\tx\t1\tx\t1\t1\t1\t5\t4\t3\t5\t7\t7\t3\t3\tx\t1\tx\t3\t3\t1\t3\t1\t3\t4\tx\tx\tx\t3\tx\t3\tx\t1\tx\t3\tx\tx\tx\t3\tx\t1\t4\t5\t6\t1\t4\t7\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t4\tx\t5\tx\tx\tx\t5\tx\t5\tx\t1\tx\t4\t1\t1\t3\t7\tx\tx\tx\t3\tx\t1\tx\t6\tx\tx\tx\t6\tx\t3\tx\tx\tx\t3\tx
x\t8\tx\t1\t3\t3\t1\t6\tx\t3\t7\t1\t3\t5\t4\t1\t7\t5\t5\t3\tx\t3\tx\t1\tx\t4\t3\t4\t1\t3\t5\t1\t5\t4\t3\t1\tx\t3\t7\t3\tx\t4\tx\t4\t5\t1\t1\t3\t3\t5\t3\t1\t1\t6\tx\t7\t7\t1\t5\t4\t6\t6\tx\t1\t3\t3\t7\t1\tx\t5\tx\t7\tx\t1\tx\t7\tx\t7\t1\t1\t3\t5\t1\t7\t4\t5\tx\t4\tx\t1\tx\t7\t7\t7\tx\t7\t7\t7\tx\t8\tx
x\t1\tx\tx\tx\t1\tx\t5\tx\t3\tx\t6\t1\t3\t5\t3\tx\t1\tx\t7\tx\t5\tx\tx\tx\t5\tx\tx\tx\t4\t4\t1\t1\t5\t1\t4\tx\t5\tx\t5\tx\t3\tx\t3\tx\t7\tx\tx\tx\tx\tx\tx\tx\t4\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\t3\tx\t7\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t7\tx\t4\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\t4\t7\t1\t5\t1\t4\t3\tx\t7\tx\t1\tx\t3\t7\t5\t5\t7\tx\t5\tx\t1\t7\t4\t1\t3\t3\t5\t1\t7\t1\t6\t5\t3\t1\t5\t1\t1\tx\t1\tx\t7\tx\t1\tx\t3\tx\t1\t3\t3\t3\t3\t3\t7\t5\t6\t1\t3\t5\t7\t5\t3\tx\t8\t1\t4\t7\t1\t1\t1\t3\t6\tx\t1\tx\t7\t3\t1\t6\t5\tx\t3\t1\t1\t6\t5\tx\t5\tx\t5\t1\t1\t5\t3\t5\t3\t7\t4\t5\t8\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
`;

const histories = [
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
</p>`,
`<p>Самые отвлечённо-умозрительные научные теории могут через какое-то время (порой — значительное!) стать основой весьма практических дел, причём выгода от только одного применения многократно окупает расходы на чудаков-математиков за всю историю науки...
<br>
Первая половина XIX века.
Ректор Казанского университета Николай Иванович Лобачевский предлагает свою «Воображаемую геометрию», в которой сумма углов треугольника не равна 180 градусам, как в существовавшей две тысячи лет геометрии Евклида. 
<br>
Начало XXI века. 
Для работы GPS-навигаторов нужны очень точные часы на спутниках орбитальной группировки, поддерживающих работу навигационной системы.
Ход часов в этих условиях изменяется благодаря сразу двум эффектам: большой скорости спутника и нахождению в гравитационном поле Земли. 
Это как про неевклидову геометрию пространства-времени. И если в какой-то момент «отключить» учёт этих эффектов, то уже за сутки работы в показаниях навигационной системы накопится ошибка порядка 10 км.
</p>`,
`<p>Математика является и языком, и главным инструментом естественных наук и техники. Математика играет эту роль и в физике, от теории до приложений, и в осуществлении космических полётов, и в укрощении атомной энергии, и в жизни компьютерного мира. 
Менее очевидна важность математики в таких дисциплинах, как медицина или лингвистика. 
Но даже читатель, догадывающийся о значительной математической «составляющей» в различных сферах деятельности, не всегда может оценить степень зависимости этих областей от математики. 
Основная причина — сложность применяемых математических инструментов, часто — специально разработанных для конкретного приложения. 
И вообще люди редко задумываются над математической «начинкой» окружающих нас предметов и явлений, а иногда и просто не замечают её.</p>`,
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
</p>`,
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
</p>`,
`<p>Многие страны столкнулись с серьёзной проблемой. Число пользователей дорог увеличилось настолько, что те перестали справляться с нагрузкой. 
<br>
Наивное представление о том, что для решения проблемы пробок достаточно увеличить количество дорог, было опровергнуто уже тогда. Математики придумали пример дорожной сети, в которой после ввода дополнительной дороги эффективность сети уменьшалась. Естественное желание автомобилистов использовать новую дорогу для выбора оптимального по времени маршрута неожиданно приводило к увеличению времени проезда для всех водителей!
См. пример в <a href="https://old.kvantik.com/art/files/pdf/2012-03.6-10.pdf" target="_blank">этой статье</a>.
Было разработано много интересных подходов к моделированию транспортных потоков с целью оптимального управления ими, 
но основой для всех предлагаемых решений являются два раздела прикладной математики — вычислительная гидродинамика и теория игр.
</p>`,
`<p>Одной из важнейших областей применений математики является криптография — наука о шифрах, т.е. способах преобразования информации, позволяющих скрывать её содержание от посторонних. 
С развитием электронных коммуникаций криптография стала предметом интереса более широкого круга потребителей: возникла необходимость защиты технических, коммерческих, персональных и других данных, передаваемых по общедоступным каналам связи.
В последние десятилетия в криптографии стали появляться шифры, стойкость которых обосновывается сложностью решения чисто математических задач: разложения больших чисел на множители, решения показательных сравнений в целых числах и других. 
Стойкость шифров зависит также и от качества генераторов случайных чисел, порождающих ключи. 
Методы и результаты различных разделов математики (в частности, алгебры, комбинаторики, теории чисел, теории алгоритмов, теории вероятностей и математической статистики) используются как при разработке шифров, так и при их исследованиях, в частности, при поиске методов вскрытия шифров. 
Криптография является богатым источником трудных математических задач, а математика — одной из основ криптографии.
История показывает, что рано или поздно развитие математических методов и техники приводит к тому, что задачи, казавшиеся неразрешимыми, находят решение. 
</p>`,
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
</p>`,
`<p>В железнодорожных составах и поездах метро, в отличие от автомобилей, в колёсной паре колёса жёстко сцеплены друг с другом осью и, соответственно, вращаются с одинаковой угловой скоростью. 
Но при повороте поезда длины путей, пройденных колёсами, будут отличаться: ведь в каждой точке поворота радиус окружности у внешнего рельса чуть больше, чем радиус внутреннего рельса. 
С другой стороны, по техническим требованиям проскальзывания колёс относительно рельсов быть не должно. 
Кажется, что отсутствие проскальзывания и разный «пробег» жёстко сцепленных колёс — несовместимые обстоятельства и что поезда просто не смогут поворачивать. 
Спасает геометрия: колёса делают не цилиндрическими, а в виде конусов.
См. <a href="https://etudes.ru/etudes/train-wheelset" target="_blank">статью с анимацией про колёсные пары</a>.
</p>`,
`<p>Работа спутниковых антенн, в частности тех, которые принимают телевизионный сигнал, основана на оптическом свойстве параболы.
Парабола — это график квадратичной функции <em>у = ах² + Ьх + с</em> (в частности, <em>у = х²</em>).
Если на параболу падает поток лучей, параллельных оси симметрии, то, отразившись от параболы, лучи придут
в фокус параболы (это такая особая точка), причём придут одновременно.
Радиосигналы от спутника идут почти параллельно (они ведь на расстоянии больше 30000км (да, 30 тыс.км!)),
а в фокусе как раз располагается небольшой приёмник, который получает все сигналы, попавшие на тарелку-антенну.
См. <a href="https://etudes.ru/sketches/parabola-optic-property/" target="_blank">анимацию</a> и
<a href="https://etudes.ru/etudes/parabolic-antenna/" target="_blank">целую статью</a>.
</p>`,
`<p>Если проследить по карте маршрут полёта самолёта из Москвы в Петропавловск-Камчатский, то можно заметить, что во время полёта самолёт забирается (по широте) высоко вверх.
<a href="https://yandex.ru/maps/-/CCUgaSdGSC" target="_blank">См. карту</a>. 
Кажется, что длина такого пути больше длины «прямого» пути, соединяющего на карте эти два города (координаты по широте близки: 55° 45' 21" с. ш. и 53° 1' с. ш.). 
Странно, ведь лишние сотни километров пути самолёта — дорогое удовольствие. 
Но и сервис «Яндекс.Карты» на запрос о расстоянии между этими городами тоже выдаёт выпуклую вверх кривую. 
Всё дело в том, что понятие кратчайшего расстояния неразрывно связано с той поверхностью, по которой оно измеряется.
(А-ха-ха, вы ведь уже читали сундук про «воображаемую геометрию»? Это снова она!)
<br>
Любая плоская карта представляет земную поверхность с искажениями. 
А рассмотрение соответствующих траекторий на глобусе позволит во всём разобраться.</p>`,
`<p>На одной из своих лекций Давид Гильберт сказал: — Каждый человек имеет некоторый определённый горизонт. Когда он сужается и становится бесконечно малым он превращается в точку.
Тогда человек говорит: «Это моя точка зрения».</p>`,
`<p>С обычными числами знакомы все.
Некоторые знакомы с комплексными числами, в которых есть специальное число <i>i</i>, квадрат которого равен минус единице!
(Те, кто не ещё знаком, но будет учиться математике, обязательно познакомится!)
Это число позволяет делать много разной магии, например, раскладывать выражение (x² + 1) на множители (получится (x + <i>i</i>) ∙ (x - <i>i</i>)).
А в 1843 году Уильям Роуэн Гамильтон придумал кватернионы: в них целых три специальных числа <i>i</i>, <i>j</i> и <i>k</i>, причём
<i>i</i>² = <i>j</i>² = <i>k</i>² = <i>ijk</i> = −1.
Эти правила позволяют определить умножение кватернионов.
В 1960 году первые ЭВМ стали использоваться на борту космических кораблей. 
И оказалось, что для расчёта вращений очень удобно использовать кватернионы!
А сейчас ставшие классикой «кватернионные» системы возвращаются на Землю, находя применения в робототехнике и даже
в современных автомобилях. Есть работа для кватернионов и в виртуальном мире — это важный инструмент в системах трёхмерной
графики и для создания компьютерных игр.
</p>`,
`<p>Передача равномерного вращательного движения с одной оси на другую — одна из основных задач в теории механизмов. 
В наручных часах важна точность преобразования угловых скоростей, в «серьёзных» машинах необходимо передавать и силовые функции.
Очень часто она решается при помощи шестерёнок.
Оказывается, что если шестерёнки должны передавать существенные усилия (скажем как в двигателе автомобиля), то форма зубцов становится очень важной!
Если выбрать форму неудачно, то шестерни будут сильно тереться друг об друга, увеличивая износ и уменьшая эффективность механизма.
В 1762 году Эйлер предложил использовать в зубчатых передачах эвольвентное зацепление, 
оказавшееся весьма удачным и ставшее самым распространённым, в основном, в больших механизмах. 
Эвольвента окружности — кривая, которую описывает конец натянутой нити, сматываемой с диска.
<br>
Вот как выглядит прокатывание одной шестерни по другой при использовании эвольвентного зацепления:
<br>
<img src="https://upload.wikimedia.org/wikipedia/commons/c/c2/Involute_wheel.gif" style="width: 80%">
<br>
Обратите внимание, направление, в которой одна шестерня давит на другую, всё время остаётся постоянным!
</p>`,
`<p>Теория вероятностей позволяет «правильно» учитывать многие процессы, подверженные случайности.
Вот типичный пример.
Представим себе тест на коронавирус, который при наличии болезни показывает положительный результат в 98% случаев (то есть примерно у 2 человек из 100 он не замечает болезнь).
А для здоровых, для не очень большого числа, скажем 10%, тоже показывает положительный результат, но ошибочно.
Может показаться удивительным, но если тест проводится на редкое
заболевание, то вероятность его наличия при положительном результате будет значительно меньше 98%! 
Например, если в эпидемию заболевание встречается у 5% населения, то она равна 34%. Дело в том,
что редкость заболевания — значимая информация, её надо учитывать, и считать следует так называемую условную вероятность.
Если больных меньше, то польза такого теста очень быстро становится нулевой: он будет ловить огромное число «здоровых»!
</p>`,
`<p>Для целой серии различных задач, часто связанных с составлением расписаний, логистикой, но не только,
используется метод, который называется «Линейное программирование».
Метод применяется настолько часто и имеет настолько большое значение, что множество математиков оптимизировали алгоритмы, с ним связанные.
Совместный эффект от развития компьютеров и математики даёт ускорение в порядка 450 миллиардов раз!
Задачи, на которые требовалось 126 лет в 1991 году, сейчас мы умеем решать за долю секунды!
Но ускорение компьютеров за это время — «всего» в 100000 раз.
То есть математика даёт ускорение в 4500000 раз!
Вот так развитие математики обогнало развитие компьютеров.
</p>`,
`<p>Великий физик и изобретатель Никола Тесла обладал феноменальной памятью и способностью визуализации. Он мог создавать и тестировать свои изобретения в уме, а затем воплощать их в реальности. Тесла заявил, что его мысленные изображения были настолько ясными и реалистичными, что иногда он испытывал трудности в отличении их от реальных объектов.</p>`,
`<p>Альберт Эйнштейн, один из самых известных физиков в истории, страдал от дислексии и считался плохим учеником в начальной школе. Он был изгнан из одной из школ и поначалу не был принят в Цюрихскую политехническую школу из-за низких результатов по некоторым предметам. Впоследствии он смог поступить туда и стать выдающимся ученым, чьи теории полностью изменили наше понимание мира.</p>`,
`<p>Галилео Галилей, итальянский астроном и физик, был одним из первых ученых, который использовал телескоп для изучения небесных объектов. В результате своих исследований он открыл четыре крупнейших спутника Юпитера, которые назвали Галилеевыми спутниками. Однако его утверждения о том, что Земля вращается вокруг Солнца, противоречили учению Католической церкви, и он был осужден инквизицией и вынужден отречься от своих взглядов.
<br>
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/Jupiter_and_the_Galilean_Satellites.jpg/375px-Jupiter_and_the_Galilean_Satellites.jpg" style="width: 80%">
</p>`,
`<p>Блез Паскаль, французский математик, философ и физик, известен своими работами в области гидродинамики, а также созданием одного из первых механических калькуляторов, называемого "Паскалин". Он также сотрудничал с французским философом и математиком Пьером де Ферма в области теории вероятностей, которая стала основой для современных статистических методов и страховых математических моделей.
<br>
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Pascaline-CnAM_823-1-IMG_1506-black.jpg/1280px-Pascaline-CnAM_823-1-IMG_1506-black.jpg" style="width: 80%">
</p>`,
`<p>В 1903 году Мария Склодовская-Кюри стала первой женщиной, которая получила Нобелевскую премию, и первым ученым, удостоенным двух Нобелевских премий. Ее первая премия была присуждена в области физики (1903 год) вместе с ее мужем Пьером Кюри и Антуаном Анри Беккерелем за исследования радиоактивности. Вторая премия была присуждена ей в 1911 году в области химии за открытие двух новых элементов, радия и полония. Мария Кюри стала символом научного прогресса и продолжает вдохновлять молодых ученых по всему миру.</p>`,
`<p>Джеймс Клерк Максвелл, шотландский физик и математик, наиболее известен своими работами в области электромагнетизма. Его уравнения Максвелла, опубликованные в середине 19 века, описывают основы классической электродинамики и предсказывают существование электромагнитных волн, которые включают в себя радио, микроволны, инфракрасное и видимое излучение. Уравнения Максвелла легли в основу современной связи и имеют огромное значение для нашей повседневной жизни.</p>`,
`<p>Томас Эдисон, известный изобретатель, однажды хотел найти подходящий материал для нити в своей электрической лампочке. Он протестировал более 6 000 различных материалов, пока не нашел тот, который работал наилучшим образом. 
Это был карбонизированной бамбук!
Лампочки
из карбонизированной бамбуковой нити горят по яркости примерно как свеча, но они горели значительно
дольше, чем любая существующая нить в то время. 
Эдисон учил нас не сдаваться и продолжать искать решения, даже если это потребует тысячи попыток.
</p>`,
`<p>Ричард Фейнман, известный теоретический физик, обладал уникальным способом объяснения сложных научных концепций. 
Он разработал так называемые "диаграммы Фейнмана", которые позволяют визуализировать сложные взаимодействия частиц. 
Фейнман был известен своими забавными и неформальными лекциями, которые делали физику интересной и доступной для многих людей.
Очень рекомендуем его книгу «Вы, конечно, шутите, мистер Фейнман!».
</p>`,
`<p>Математика играет ключевую роль в прогнозировании погоды и анализе климатических изменений. Метеорологи используют сложные математические модели для анализа и предсказания атмосферных условий на основе большого количества данных.
В основе метеорологических моделей лежат системы дифференциальных уравнений, которые описывают физические законы, управляющие атмосферными процессами. Эти уравнения объединяют такие факторы, как температура, атмосферное давление, влажность, ветер и другие переменные.
Поскольку аналитическое решение систем дифференциальных уравнений для атмосферы обычно невозможно, метеорологи применяют численные методы для приближенного решения этих уравнений. Компьютеры выполняют миллионы вычислений для получения решений, которые предсказывают состояние атмосферы на определенное время в будущем.
</p>`,
`<p>Современную медицину сложно представить без математики.
Вернее потребителям представить легко, а вот создателям — никак.
Каждое новое лекарство и новый прибор должны пройти клинические испытания.
Где с помощью статистики и вероятности медицинские специалисты могут определить эффективность лечения, 
оценить риски и прогнозировать возникновение определенных заболеваний.
</p>`,
`<p>Геодезия – это наука, занимающаяся измерением и представлением Земли в виде геометрической модели. 
Геодезисты определяют точные координаты различных объектов на поверхности планеты и измеряют расстояния между ними. 
В геодезии математика играет ключевую роль.
Геодезисты часто используют геометрию и тригонометрию для расчета расстояний и углов между точками на Земной поверхности. 
Например, с помощью тригонометрических функций они могут определить высоту горы или глубину каньона.
А ещё в геодезии также применяется теория графов для анализа и оптимизации транспортных сетей, расположения городов и других объектов. 
Это помогает создавать более эффективные планы развития территорий и улучшать инфраструктуру.</p>`,
`<p>Математика играет важную роль в исследованиях коммерческих компаний, помогая анализировать данные и принимать обоснованные решения. 
Один из распространенных методов – A/B тестирование, которое использует статистику для сравнения двух вариантов продукта, дизайна сайта или других элементов маркетинга.
С помощью A/B тестов компании могут определить, какой вариант лучше работает для достижения определенной цели, например, увеличения продаж или улучшения пользовательского опыта. 
В процессе тестирования собираются данные о поведении пользователей, которые затем анализируются с использованием математических методов.
В результате развитие компании получается более... целенаправленным!
</p>`,
`<p>Математика является неотъемлемой частью строительства зданий, 
так как она помогает архитекторам и инженерам проектировать безопасные и функциональные сооружения. 
Геометрия используется для создания планов и разработки форм зданий, а также для расчета углов и длин стен.
<br>
Алгебра и тригонометрия помогают в расчете необходимых материалов и определении нагрузок на различные части здания, 
что важно для обеспечения его прочности и стабильности. 
В целом, математика играет ключевую роль в обеспечении безопасности, красоты и устойчивости зданий, которые мы видим и используем каждый день.</p>`,
`<p>До появления компьютеров математика играла ключевую роль в навигации на кораблях. Моряки использовали методы тригонометрии для определения своего местоположения и направления движения. Они измеряли углы между звездами и горизонтом с помощью секстанта, инструмента, который позволял точно определить углы.
<br>
Определение широты и долготы было основной задачей в навигации. Широту можно было определить по высоте Полярной звезды или Солнца над горизонтом, а долготу — с помощью хронометра, точных часов, которые позволяли морякам учесть разницу во времени между их местоположением и исходной точкой.
</p>`,
`<p>— Почему растения ненавидят математику?
<br>— Они с трудом выносят, когда люди ищут корни.
<br>
Эту шутку придумала ChatGPT.
GPT расшифровывается как Generative Pre-trained Transformer, или «трансформер, обученный для генерации».
ChatGPT — большая языковая модель, для тренировки которой использованы миллионы текстов и... и очень много математики!
Всё машинное обучение пронизано математикой и магией!
Математики больше: линейная алгебра, математический анализ и т.п.
<br>
Можно посмотреть как <a href="https://shashkovs.ru/ai/">очень маленькая нейронная сеть</a> управляет змейкой.
Чем больше сеть, тем полее хитрые штуки она может делать.
У ChatGPT около 80-100 миллиардов таких «шариков» и около 100 триллионов связей между ними.
</p>`,
`Известный американский физик и математик, один из создателей векторного анализа Джозайя Гиббс (1839–1903), был очень неразговорчивым человеком и обычно молчал на заседаниях Ученого Совета Йельского университета, в котором преподавал. Но однажды он не сдержался. На одном из заседаний зашел спор о том, чему больше уделять внимания в новых программах — иностранным языкам или математике. Не выдержав, Гиббс поднялся с места и произнес целую речь: «Математика — это язык!»`,
`Когда Харди навещал в больнице Рамануджана, он, по его словам, начал разговор с того, что «пожаловался» на то, что приехал на такси со скучным, непримечательным номером «1729». Рамануджан разволновался и воскликнул: «Харди, ну как же, Харди, это же число — наименьшее натуральное число, представимое в виде суммы кубов двумя различными способами!». Вот эти способы: 1729 = 1³ + 12³ = 9³ + 10³`,
`С именем знаменитого Пьера Ферма связано много тайн. Однажды он получил письмо с вопросом: «Является ли простым число 100895598169?» Ферма незамедлительно ответил, что это двенадцатизначное число является произведением двух простых чисел: 898423 и 112303. Способ исследования числа он не раскрыл.<br><a href="http://kvant.mccme.ru/1972/07/tak_ili_ne_tak_dejstvoval_ferm.htm" target="_blank">Продолжение истории</a>.`,
`Что лучше: вечное блаженство или бутерброд с ветчиной? На первый взгляд кажется, что вечное блаженство лучше, но в действительности можно доказать, что это не так! Судите сами. Что лучше вечного блаженства? <i>Ничего</i>. А бутербод с ветчиной лучше, чем <i>ничего</i>. Следовательно, бутерброд с ветчиной лучше, чем вечное блаженство.`,
`Когда математик Джордж Данциг был еще студентом, он часто засиживался за занятиями до поздней ночи. Однажды он из-за этого проспал и опоздал на полчаса на лекцию профессора Неймана. Усевшись за парту Джордж быстро переписал две задачи с доски, решив, что это домашнее задание. Задачи были очень сложны, но к следующему занятию он всё-таки их сделал. Когда он принёс решения профессору, Нейман молча взял листки с решениями и убрал в портфель, так что Джордж решил, что профессор всё ещё сердится на него за то опоздание. А через несколько недель профессор Нейман с криком ворвался в дом Джорджа в шесть утра! Оказалось, что студент Джордж Данциг нашёл правильное решение двух задач из области математический статистики, которые до тех пор считались неразрешимыми. Сам Джордж об этом и не подозревал, так как на занятие опоздал и не слышал, что говорил профессор Нейман о задачах на доске. Он попросту не знал о репутации этих двух задач!`,
`Любые две грани тетраэдра имеют общее ребро, а любые две вершины соединены общим ребром.
А может ли быть какой-то другой многогранник у которого любые две грани имеют общее ребро?
Пока удалось построить только один такой многогранник: в 1977 году Лайош Силлаши построил полиэдральный тор (многогранник Силлаши).
<br>
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/7/72/Szilassi_polyhedron.gif/220px-Szilassi_polyhedron.gif">
<br>
У нас в 179-й школе есть крупная модель этого многогранника. Может быть, вам удастся уговорить кого-нибудь из старших преподавателей вам её показать?`,
`В 1852 году английский ботаник и логик Фрэнсис Гутри работал в типографии. При составлении карты графств Англии, он обратил внимание, что для такой цели хватает четырёх красок.
Гутри рассказал об этом своему брату, а тот — известному математику Августу де Моргану.
Де Морган заинтересовался вопросом: можно ли любую карту покрасить в 4 цвета?
От него этот забавный вопрос стал известен математикам Англии, и довольно неожиданно оказалось, что, несмотря на внешнюю простоту, доказать утверждение никак не получается.
В 1878 году Артур Кэли официально сформулировал «Проблему четырёх красок».
За решение проблемы брались самые авторитетные математики не только Англии, но и мира.
Несколько раз задача объявлялась решённой, но затем в решений находили ошибку. Ошибки исправлялись, но годы спустя обнаруживались новые — в исправленных решениях.
Теорема о четырёх красках была доказана только через 100 лет, в 1976 году — и стала первой математической теоремой, доказанной с помощью компьютерных вычислений.`,
`Гугол — это число вида 100...00 со 100 нулями.
В 1938 году известный американский математик Эдвард Казнер гулял по парку с двумя своими племянниками и обсуждал с ними большие числа. В ходе разговора зашла речь о числе со ста нулями, у которого не было собственного названия. Один из племянников, девятилетний Милтон Сиротта, предложил назвать это число «гугол» (англ. googol). 
Термин «гугол» не имеет серьёзного теоретического и практического значения. Казнер предложил его для того, чтобы проиллюстрировать разницу между невообразимо большим числом и бесконечностью: гугол больше, чем количество атомов в известной нам части Вселенной, которых, по разным оценкам, насчитывается от 10⁷⁹ до 10⁸¹.
Название компании Google является искажённым написанием слова «googol». Создатели известной поисковой машины хотели использовать термин «googol» в качестве названия, но при регистрации выяснилось, что такой домен уже занят.`,
`Пожалуй, один из лучших ответов на вопрос «Кому нужна математика?» дал математик по имени Мартин Гротшел.
Как-то раз немецкое правительство решило выделить целевым образом значительные суммы на развитие самых
передовых и необходимых областей науки. На заседание государственной комиссии были приглашены представители всех наук. Гротшел представлял математику и выступал последним. Заседание уже подходило к концу, чиновники сидели осоловевшие от обрушенного на них потока информации и энтузиазма ораторов. Гротшел вышел на трибуну и сказал примерно следующее:
<br>
— Уважаемые господа! Я не буду утомлять вас длинной речью, а просто приведу пример. Недавно мы получили заказ от большой страховой компании, планирующей создать автосервис для своих клиентов. Идея очень проста: если у клиента в дороге сломалась машина, он может позвонить по телефону и к нему тут же приедет аварийная служба. Вопрос в том, как правильно организовать такой сервис. В принципе, задачу можно решить довольно просто — например, приставить к каждому клиенту личную аварийную машину с механиком. Тогда клиент в любой момент немедленно получит помощь. Но это очень дорого! Другой вариант — вообще не связываться с аварийным сервисом. Клиенты могут ждать до бесконечности, зато это не будет стоить им ни цента. Так вот. Если вас эти решения не устраивают, то я должен вам сообщить, что для любых других вариантов понадобится математика! Спасибо за внимание.`,
`Легковой автомобиль — довольно сложная штука. И вот оказывается, сделать так, чтобы он мог поворачивать без проскальзывания колёс, не получится без геометрии! При повороте передние колёса не параллельны друг другу и поворачиваются каждое на свой угол. Механическую конструкцию, которая обеспечивает поворот колёс на нужный угол, придумал француз, каретных дел мастер Шарль Жанто (Charles Jeantand). Однако для карет, передвигавшихся с малыми скоростями, это было не так существенно, как для машин, и изобретение Жанто было забыто. Лишь почти через три четверти века два отца автомобилестроения, два немца, два инженера — Готтлиб Даймлер (Gottlieb Wilhelm Daimler) и Карл Бенц (Karl Friedrich Michael Benz) — изобретая свои автомобили, возвращаются к трапеции Жанто. В 1889 году Даймлер получает патент на «способ независимого управления передними колёсами с разновеликими радиусами поворота».
<br>
На сайте <a href="https://etudes.ru/etudes/steering-geometry/" target="_blank">математических этюдов</a> есть подробности про эту конструкцию.`,
`Имя Николая Ивановича Лобачевского не гремело в мировом научном сообществе, пока он был жив. Современник Пушкина и Пирогова, он не получал премий, о нем не писали на первых полосах газет, хотя как ректор одного из ведущих российских университетов он был известен — как в Казани, так и за ее пределами. Первые публикации Лобачевского по неевклидовой геометрии вышли в 1829–1830 гг. в журнале «Казанский вестник»
Что же такое неевклидова геометрия? Это — геометрическая теория, основанная на тех же основных аксиомах, что и обычная евклидова геометрия, за исключением аксиомы о параллельных прямых.
В аксиоме «На плоскости через точку, не лежащую на данной прямой, можно провести ровно одну прямую, параллельную данной» концовка заменена на «можно провести по крайней мере две прямые, не пересекающие данную».
Оказывается, геометрия Лобачевского связана со специальной теорией относительности, без хорошего понимания которой невозможно сделать GPS.`,
`Неваляшка возвращается в своё исходное положение благодаря грузу внизу игрушки. А в 2006-м году венгерские математики Домокош и Варконьи придумали пример выпуклого тела (без полостей и «грузов»), обладающее этим свойством. Они назвали его гё́мбёц. На это у них ушло 10 лет.<br><a href="https://www.youtube.com/watch?v=J-5TIS49Kt8&t=1s" target="_blank">О гёмбёце рассказывает математик Николай Андреев</a>`,
`Паркетом называют разбиение плоскости на многоугольники так, что любые две фигуры пересекаются либо по целой стороне, либо по вершине, либо не пересекаются вообще. Разумеется, придумать таких разбиений можно очень много, но математиков интересуют только достаточно симметричные паркеты. Легко придумать паркет из треугольников (любых) или прямоугольников. Однако наиболее сложный случай паркета на плоскости — это пятиугольный паркет. В 1918 году Карл Райнхардт описал пять классов таких паркетов. Долгое время этот список считался полным, пока в 1968 году Роберт Кершнер вдруг не обнаружил еще три таких класса. В 1975 году математик Ричард Джеймс увеличил это число до девяти. Тут в истории начинается самое интересное — об открытии Джеймса написал журнал Scientific American.
Статью увидела Мардж Райс, американская домохозяйка и по совместительству математик-любитель. Разработав собственную систему записи пятиугольных замощений она за 10 лет довела их количество до 14. И вот, наконец, спустя 30 лет ученые из Вашингтонского университета в Ботелле открыли 15-е замощение. Сделали они это с помощью компьютера. И вот наконец в июле 2017 года стало известно, что француз Михаэль Рао доказал, что ничего, кроме этих семейств, нет.
<br>
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/PentagonTilings15.svg/1920px-PentagonTilings15.svg.png" style="width:100%">
`,
`Формулу для площади круга можно запомнить при помощи пиццы. Пицца радиусом <i>ц</i> и толщиной <i>а</i> имеет объём <i>пи</i>∙<i>ц</i>∙<i>ц</i>∙<i>а</i> = 𝜋 ц²∙a`,
`Известный немецкий алгебраист Эрнст Эдуард Куммер (1810–1893) очень плохо умел считать в уме. Если при чтении лекции ему надо было выполнить простенький расчет, он обычно прибегал к помощи студентов.
Однажды ему надо было умножить 7 на 9. Он начал вслух рассуждать:
<br>
— Гм... это не может быть 61, потому что 61 — простое число. Это не может быть и 65, потому что 65 делится на 5. 67 — тоже простое число, а 69 — явно слишком много. Остается только 63...`,
`Рассказывают, что знаменитый французский математик и просветитель Жан Даламбер (1717–1783) каждый раз, когда излагал студентам собственную теорему, неизменно говорил: «А сейчас, господа, мы переходим к теореме, имя которой я имею честь носить!»`,
`Многие известные физики-теоретики отличались незаурядными математическими способностями. Одним из них был нобелевский лауреат Поль Дирак.
Дирак, будучи еще студентом, участвовал в математическом конкурсе, где в числе других была и такая задача.
<br>
Три рыбака наловили рыбы и легли спать. Первый из них проснулся утром и решил уехать домой. Своих товарищей он не стал будить, а разделил всю рыбу на три части. Но при этом одна рыба оказалась лишней. Недолго думая, он швырнул ее в воду, забрал свою часть и уехал домой. Потом проснулся второй рыбак. Он не знал, что первый рыбак уже уехал, и тоже поделил всю рыбу на три равные части, и, конечно, одна рыба оказалась лишней. Он тоже закинул он ее подальше от берега и со своей долей удалился. Последний рыбак тоже не заметил, что его товарищей уже нет. Разделил ее на три равные части, выбросил одну лишнюю рыбу в воду, забрал свою долю и был таков.
В задаче спрашивалось, какое наименьшее количество рыб могло быть у рыбаков.
<br>
Дирак предложил такое решение: рыб было (–2). После того как первый рыбак совершил поступок, швырнув одну рыбу в воду, их стало (–2) – 1 = –3. Потом он ушел, унося под мышкой (–1) рыбу. Рыб стало (–3) – (–1) = –2. Второй и третий рыбаки просто повторили поступок их товарища.`,
`Однажды к Эрнесту Резерфорду за помощью обратился его коллега из Копенгагена, который принимал экзамен по физике и собирался поставить студенту неуд, но студент был категорически не согласен и говорил, что заслуживает высший балл.
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
`<p>
Многие открытия в математике и физике проживали такую историю:
<br>
Могли бы открыть, но не открыли.<br>
Открыли, но не заметили.<br>
Заметили, но не поверили.<br>
Поверили, но… не заинтересовались.<br>
У-у-у-у!!!
</p>`,
];

const chestsAsObj = [
    {x:95,y:1,bonus:4,amount:8,html:histories[44]},
{x:5,y:3,bonus:4,amount:8,html:histories[0]},
{x:73,y:3,bonus:4,amount:8,html:histories[47]},
{x:83,y:3,bonus:4,amount:8,html:histories[13]},
{x:7,y:5,bonus:4,amount:8,html:histories[7]},
{x:31,y:7,bonus:4,amount:8,html:histories[41]},
{x:3,y:9,bonus:4,amount:8,html:histories[26]},
{x:9,y:9,bonus:4,amount:8,html:histories[49]},
{x:53,y:9,bonus:4,amount:8,html:histories[21]},
{x:45,y:11,bonus:4,amount:8,html:histories[30]},
{x:5,y:13,bonus:4,amount:8,html:histories[42]},
{x:15,y:13,bonus:4,amount:8,html:histories[18]},
{x:39,y:13,bonus:4,amount:8,html:histories[25]},
{x:21,y:17,bonus:4,amount:8,html:histories[10]},
{x:5,y:19,bonus:4,amount:8,html:histories[2]},
{x:41,y:19,bonus:4,amount:8,html:histories[16]},
{x:87,y:19,bonus:4,amount:8,html:histories[45]},
{x:25,y:21,bonus:4,amount:8,html:histories[4]},
{x:49,y:21,bonus:4,amount:8,html:histories[29]},
{x:3,y:23,bonus:4,amount:8,html:histories[1]},
{x:65,y:23,bonus:4,amount:8,html:histories[35]},
{x:65,y:33,bonus:4,amount:8,html:histories[12]},
{x:85,y:33,bonus:4,amount:8,html:histories[6]},
{x:21,y:35,bonus:4,amount:8,html:histories[17]},
{x:1,y:41,bonus:4,amount:8,html:histories[32]},
{x:5,y:43,bonus:4,amount:8,html:histories[3]},
{x:49,y:43,bonus:4,amount:8,html:histories[40]},
{x:47,y:45,bonus:4,amount:8,html:histories[38]},
{x:3,y:49,bonus:4,amount:8,html:histories[31]},
{x:35,y:49,bonus:4,amount:8,html:histories[37]},
{x:33,y:53,bonus:4,amount:8,html:histories[19]},
{x:77,y:53,bonus:4,amount:8,html:histories[43]},
{x:1,y:55,bonus:4,amount:8,html:histories[9]},
{x:87,y:61,bonus:4,amount:8,html:histories[27]},
{x:79,y:65,bonus:4,amount:8,html:histories[11]},
{x:7,y:67,bonus:4,amount:8,html:histories[22]},
{x:51,y:67,bonus:4,amount:8,html:histories[46]},
{x:47,y:73,bonus:4,amount:8,html:histories[23]},
{x:73,y:73,bonus:4,amount:8,html:histories[24]},
{x:75,y:75,bonus:4,amount:8,html:histories[34]},
{x:13,y:77,bonus:4,amount:8,html:histories[33]},
{x:27,y:79,bonus:4,amount:8,html:histories[28]},
{x:9,y:85,bonus:4,amount:8,html:histories[15]},
{x:97,y:85,bonus:4,amount:8,html:histories[8]},
{x:49,y:87,bonus:4,amount:8,html:histories[36]},
{x:39,y:95,bonus:4,amount:8,html:histories[39]},
{x:1,y:97,bonus:4,amount:8,html:histories[5]},
{x:99,y:97,bonus:4,amount:8,html:histories[48]},
{x:63,y:99,bonus:4,amount:8,html:histories[20]},
{x:99,y:99,bonus:4,amount:8,html:histories[14]},
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
