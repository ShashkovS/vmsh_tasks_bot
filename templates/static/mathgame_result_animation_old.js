"use strict";

const CELL_SIZE_IN_REM = 2;
const MODAL_WIDTH_IN_CELLS = 5;
const MODAL_HEIGHT_IN_CELLS = 3;
const FOG_OF_WAR = 7;
const FOR_OPACITY_LEN = 7;

const DEBUG = false;

const mapAsString = `
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\to\to\to\t1\t1\t1\t1\t1\t1\tx\t1\t1\t2\t1\t1\t1\t2\t1\t8\tx\t1\t2\t1\tx\t2\tx\t1\t1\t1\t2\t1\tx\t1\t2\t2\t1\t1\t2\t1\t2\t1\t1\t2\t2\t1\t1\t1\t1\t8\tx\t1\t2\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t2\t1\tx\t1\tx\t5\tx\t2\t1\t3\tx\t1\tx\t5\tx\t2\t1\t1\t1\t1\t2\t5\t2\t8\tx\t2\tx\t3\tx\t1\t1\t1\t1\t5\tx
x\to\to\to\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\t2\tx\t3\tx\t1\tx\t2\tx
x\to\to\to\tx\t1\tx\t1\tx\t1\t1\t2\tx\t1\t1\t1\tx\t2\tx\t1\tx\t1\tx\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t2\tx\t1\tx\t2\t1\t2\t1\t1\tx\t1\tx\t1\t1\t1\t2\t1\tx\t1\t1\t1\t2\t1\tx\t8\tx\t1\tx\t1\t1\t1\t1\t5\tx\t1\tx\t1\tx\t1\tx\t2\t1\t1\tx\t1\t1\t3\tx\t3\t1\t1\t1\t1\t1\t2\t2\t5\tx\t1\tx\t1\tx\t1\tx
x\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\t1\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t2\t1\t1\t2\tx\t2\tx\t1\tx\t1\t1\t8\tx\t1\tx\t1\t2\t1\tx\t1\t1\t2\t1\t1\t1\t2\tx\t2\tx\t2\t2\t1\t1\t2\tx\t1\tx\t2\tx\t1\tx\t1\tx\t3\tx\t2\t5\t1\tx\t1\t2\t1\tx\t1\t1\t1\tx\t5\t1\t1\t1\t2\t2\t2\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\t1\t3\t5\t1\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t5\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t5\tx\t3\tx\t1\tx\tx\tx\t2\tx
x\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t2\tx\t1\t1\t1\tx\t1\t2\t1\t2\t1\t2\t1\t1\t1\tx\t1\t2\t1\t1\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\t1\tx\t1\tx\t1\tx\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t2\t1\t1\tx\t1\t5\t2\tx\t3\t1\t5\t1\t1\t5\t8\tx\t5\t1\t1\t2\t3\tx\t2\tx\t5\tx\t1\tx\t2\tx\t2\t2\t5\t1\t2\tx\t1\tx\t5\tx\t1\tx
x\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\t1\tx\t1\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t3\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t3\tx
x\t8\tx\t1\t1\t1\tx\t1\t1\t1\t2\t1\t2\t2\tx\t2\tx\t1\t1\t1\t2\t1\tx\t1\tx\t1\t2\t1\tx\t1\t2\t1\t2\t2\tx\t1\tx\t1\t1\t1\tx\t1\tx\t2\t1\t1\tx\t1\tx\t2\tx\t2\tx\t2\t5\t1\t1\t1\t3\t1\t3\t5\t1\t1\tx\t5\tx\t1\t1\t1\t1\t1\t1\t3\tx\t2\tx\t2\t2\t5\t1\t5\t1\t1\t2\t2\t1\t5\tx\t2\tx\t1\t1\t3\tx\t2\tx\t5\tx\t1\tx
x\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t5\tx\t1\tx
x\t1\tx\t2\tx\t1\t1\t1\tx\t1\tx\t1\t1\t2\tx\t2\t1\t2\tx\t2\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t2\t1\t1\tx\t1\t1\t2\tx\t1\t1\t2\t1\t1\tx\t1\t2\t5\t1\t1\tx\t5\tx\t1\t1\t1\t1\t2\t5\t1\t2\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t3\t2\t1\t5\t1\tx\t2\t3\t1\tx\t2\t1\t1\tx\t1\tx\t1\tx
x\t1\tx\tx\t1\t1\t2\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t5\tx\t5\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\t5\tx\t2\tx\t3\tx
x\t2\tx\t1\t1\t1\t1\t1\t1\t1\t2\t1\t1\t1\tx\t1\tx\t1\t1\t1\t1\t2\tx\t1\tx\t1\tx\t1\tx\t2\tx\t1\t1\t2\tx\t2\t1\t1\tx\t1\tx\t1\t2\t1\t1\t1\t1\t1\tx\t2\t1\t1\t1\t8\tx\t2\tx\t2\t1\t2\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t2\t1\t3\t2\t1\t2\tx\t2\tx\t1\t1\t1\tx\t1\t1\t1\t2\t2\tx\t8\tx\t1\tx\t1\tx\t1\tx\t3\t1\t2\tx
x\t1\tx\tx\t1\t1\t2\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t3\tx\t1\tx\tx\tx
x\t1\tx\t1\tx\t2\tx\t2\tx\t1\tx\t1\tx\t1\tx\t2\t2\t1\t1\t1\tx\t1\t1\t8\tx\t1\t2\t1\t1\t1\t1\t1\t1\t2\t1\t2\t1\t1\tx\t1\tx\t2\tx\t2\t1\t2\t1\t1\t2\t1\tx\t1\tx\t1\t1\t1\tx\t2\tx\t2\t1\t1\tx\t1\t1\t1\tx\t1\t1\t5\tx\t2\t1\t1\tx\t2\t1\t1\t1\t2\t3\t5\tx\t1\t1\t1\t1\t1\t1\t3\t1\t2\t1\t1\t1\t1\tx\t1\t2\t1\tx
x\t2\tx\t2\tx\t2\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t5\tx\t3\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\t8\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx
x\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t2\t1\tx\t1\tx\t1\tx\t1\t1\t2\t2\t1\tx\t2\tx\t1\tx\t2\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\t2\t1\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\t2\t1\t1\t5\t1\t1\t2\t2\t5\tx\t1\t2\t1\tx\t5\tx\t1\t1\t1\t2\t1\t1\t1\tx\t3\tx\t3\tx\t3\tx\t1\t2\t1\tx\t1\tx\t1\t1\t2\tx\t2\t2\t1\tx\t3\t1\t1\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t2\tx\tx\tx\t5\tx\t1\tx\t2\tx\t2\tx\t5\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx
x\t2\tx\t2\t2\t1\tx\t1\t2\t1\tx\t2\t1\t1\tx\t1\t2\t1\t1\t2\tx\t2\tx\t1\tx\t2\tx\t1\t1\t1\tx\t1\t2\t1\tx\t1\t2\t1\tx\t1\t2\t1\tx\t1\tx\t2\tx\t1\t1\t1\tx\t1\tx\t1\tx\t2\t3\t5\tx\t2\t3\t2\t2\t1\tx\t1\t1\t1\t3\t1\tx\t1\tx\t2\t1\t1\tx\t2\t3\t2\tx\t5\t2\t1\t1\t3\tx\t2\t1\t1\t1\t1\t5\t1\tx\t1\t1\t1\tx\t3\tx
x\t2\tx\t1\tx\t2\t1\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t2\tx\t1\tx\t2\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t5\tx\t2\tx
x\t1\tx\t1\tx\t1\t1\t2\t1\t1\t1\t1\t1\t2\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\t2\t2\tx\t1\t1\t1\t1\t1\tx\t1\t2\t2\t1\t1\t1\t1\t2\t2\t1\t1\t1\t1\t1\t1\t2\t8\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\tx\t2\tx\t1\tx\t1\t1\t2\tx\t2\t1\t1\tx\t1\tx\t1\t2\t1\tx\t3\tx\t1\tx\t1\tx\t1\t1\t2\tx\t2\t1\t1\tx\t1\tx\t2\t1\t1\t2\t1\tx
x\t2\tx\tx\tx\t1\t1\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t3\tx
x\t1\t1\t2\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t2\t1\t2\t1\t1\t1\t2\tx\t1\t2\t1\tx\t2\t1\t2\tx\t1\t1\t1\t2\t1\tx\t1\t1\t1\tx\t2\tx\t1\tx\t2\tx\t1\t1\t3\tx\t5\t3\t1\tx\t2\tx\t1\tx\t2\t2\t2\tx\t1\tx\t8\tx\t2\tx\t1\t3\t1\t1\t1\t1\t1\t5\t1\t1\t2\t2\t2\tx\t1\t1\t1\tx\t1\t1\t2\tx\t1\tx
x\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx
x\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t2\t1\tx\t1\tx\t1\tx\t1\tx\t1\t2\t1\t1\t1\tx\t1\t2\t1\t1\t1\tx\t1\t1\t1\tx\t2\t1\t1\t2\t1\tx\t3\t1\t1\t2\t1\tx\t1\t1\t1\tx\t1\tx\t3\tx\t2\t1\t5\tx\t1\tx\t2\t1\t2\t2\t2\tx\t2\tx\t1\t1\t5\tx\t3\t2\t1\t1\t3\t1\t2\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx
x\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t3\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\t2\tx
x\t1\t2\t2\t1\t1\tx\t2\t1\t2\tx\t8\t1\t1\t1\t1\tx\t1\t2\t1\tx\t1\tx\t1\t1\t1\t1\t2\tx\t2\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t2\t1\tx\t2\t2\t1\t1\t2\tx\t1\tx\t1\t1\t1\t1\t3\tx\t1\tx\t1\tx\t1\t1\t3\t1\t3\tx\t2\tx\t2\t1\t1\t5\t1\tx\t2\tx\t1\tx\t1\tx\t5\t5\t5\t1\t1\tx\t2\t2\t2\tx\t1\t1\t1\t2\t1\t2\t1\tx\t2\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx
x\t2\t1\t2\tx\t2\t1\t1\tx\t1\tx\t1\t1\t1\tx\t2\t2\t2\tx\t1\tx\t1\t2\t1\tx\t2\t1\t1\t1\t1\t1\t1\tx\t1\tx\t2\t1\t1\tx\t1\t2\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t5\tx\t2\t1\t1\t2\t1\tx\t5\t1\t1\t3\t5\t1\t1\tx\t2\tx\t1\t1\t2\tx\t2\t5\t1\tx\t2\t2\t2\tx\t5\t2\t2\tx\t3\t2\t2\t1\t1\t1\t1\tx\t1\tx\t2\tx
x\t2\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t5\tx\tx\tx\tx\tx\t3\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t2\tx
x\t1\tx\t8\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t2\t1\t1\tx\t2\t1\t2\tx\t2\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t2\tx\t1\tx\t1\t1\t2\tx\t2\tx\t1\t1\t2\tx\t8\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t2\t2\t1\t2\t1\tx\t2\tx\t1\t2\t2\tx\t2\t2\t1\t5\t1\t2\t2\t2\t2\t1\t3\t1\t1\t2\t1\tx\t1\tx\t1\t2\t1\tx
x\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\t1\tx\t2\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\t5\tx\tx\tx\tx\tx\t1\tx\t3\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx
x\t1\tx\t2\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t2\t1\t1\t1\t2\tx\t2\tx\t2\tx\t2\tx\t1\tx\t2\tx\t2\t1\t1\tx\t1\t1\t1\tx\t1\t2\t2\tx\t1\t1\t2\tx\t1\t1\t1\tx\t1\t1\t2\t3\t2\t2\t1\tx\t3\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t3\t1\tx\t1\t1\t1\t2\t1\tx\t2\t1\t1\tx\t1\t1\t3\t2\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t2\tx
x\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\t5\tx
x\t2\t2\t2\t1\t1\t1\t1\tx\t1\t1\t1\t1\t2\t1\t2\tx\t2\t1\t1\t2\t1\tx\t1\t1\t1\t1\t1\tx\t1\t2\t2\tx\t2\t1\t1\tx\t1\tx\t8\tx\t1\tx\t1\t1\t1\t2\t1\tx\t2\t1\t1\tx\t1\t2\t3\t2\t5\t1\t2\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t5\t1\t1\tx\t2\tx\t2\t1\t3\t1\t5\tx\t1\t2\t2\tx\t2\t5\t1\tx\t1\t1\t1\t1\t2\tx
x\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\t5\tx\tx\tx\t3\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\t3\tx\t1\tx\tx\tx\tx\tx
x\t1\tx\t1\tx\t1\t2\t1\tx\t1\tx\t1\tx\t1\t1\t2\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t2\tx\t1\t1\t2\t1\t1\t1\t1\tx\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t3\t1\tx\t1\t3\t1\tx\t1\t1\t1\tx\t5\tx\t1\tx\t2\tx\t1\t1\t2\tx\t1\t1\t1\t1\t2\t2\t2\tx\t2\t1\t2\tx\t1\t1\t5\tx\t2\tx\t1\t1\t5\t1\t1\t5\t1\tx
x\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t2\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t2\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx
x\t1\t1\t1\tx\t1\t1\t2\tx\t2\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t2\tx\t1\t1\t2\t1\t1\tx\t1\tx\t2\t2\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t2\t1\t2\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t3\t1\tx\t1\t2\t1\tx\t1\tx\t8\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t5\tx\t5\t2\t1\tx\t8\t1\t1\tx
x\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx
x\t1\t1\t1\tx\t2\t2\t1\tx\t1\t1\t1\t1\t1\t1\t1\t2\t8\tx\t2\t1\t2\tx\t1\t1\t1\tx\t1\tx\t2\t1\t1\tx\t1\t1\t1\tx\t1\t2\t2\t1\t1\tx\t1\t1\t1\t1\t1\t2\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t2\tx\t1\t1\t1\tx\t1\tx\t1\t1\t2\t3\t1\t3\t1\tx\t2\t1\t1\t1\t5\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t2\t1\t1\t2\t1\tx
x\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx
x\t1\t1\t2\t2\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t2\t1\t1\tx\t1\t1\t1\tx\t1\tx\t8\tx\t1\t1\t8\tx\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t2\tx\t1\t1\t2\t2\t1\tx\t1\t1\t1\t1\t1\t2\t1\t1\t1\t2\t1\tx\t1\tx\t2\tx\t2\tx\t2\t5\t1\t2\t1\t2\t1\tx\t2\t1\t5\t1\t2\tx\t2\t1\t1\tx\t1\tx\t1\tx
x\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t2\tx\tx\tx\t2\tx\t1\tx\t1\tx\tx\tx
x\t1\tx\t1\tx\t1\t2\t2\t2\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t2\tx\t1\tx\t2\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t2\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t2\tx\t1\t1\t1\tx\t8\tx\t1\tx\t1\t1\t1\tx\t1\tx\t2\t1\t2\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\t1\tx\t1\t1\t1\t1\t2\tx\t3\t1\t2\t1\t1\tx
x\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\t3\tx\tx\tx\t2\tx\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\t2\t2\tx\t1\t1\t2\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t2\t1\t1\tx\t1\t1\t1\t2\t1\tx\t1\t1\t1\tx\t1\tx\t2\tx\t1\t1\t1\tx\t1\t1\t1\t1\t2\t1\t1\tx\t1\tx\t1\tx\t1\t2\t1\t1\t1\tx\t1\t1\t1\tx\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t2\t1\t2\t2\t2\t1\t1\t2\t1\tx\t2\tx\t1\t1\t1\tx\t2\tx\t3\tx
x\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t5\tx\tx\tx\tx\tx\t3\tx\t2\tx
x\t2\t1\t8\tx\t2\t1\t1\tx\t1\tx\t2\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\t2\t1\tx\t2\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t2\t1\t1\t1\t2\t1\t1\t1\t1\t1\t1\t2\t1\tx\t1\t1\t1\tx\t2\t2\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t2\tx\t1\t1\t1\tx\t1\t2\t2\tx\t1\tx\t1\tx\t2\tx\t2\t3\t1\t1\t2\tx\t1\t1\t1\tx\t1\tx
x\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\t2\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t5\tx\tx\tx\tx\tx\tx\tx\t3\tx\t1\tx\tx\tx\t1\tx
x\t1\t1\t2\tx\t1\t1\t1\tx\t2\tx\t2\tx\t1\t1\t1\tx\t2\tx\t1\t1\t1\tx\t2\tx\t1\t1\t1\tx\t1\tx\t2\t1\t1\tx\t2\tx\t1\t1\t1\t1\t1\tx\t1\tx\t1\t2\t1\tx\t2\tx\t2\t1\t1\t1\t1\t1\t1\t2\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t2\tx\t1\tx\t1\tx\t1\tx\t5\tx\t1\t3\t1\tx\t2\tx\t1\tx\t1\t1\t1\t2\t2\t1\t1\t1\t1\tx\t2\t1\t1\tx
x\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\t2\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx
x\t1\tx\t1\tx\t2\tx\t2\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t8\tx\t1\t1\t1\tx\t2\t1\t1\tx\t1\t1\t2\t1\t1\t1\t2\tx\t1\tx\t1\tx\t1\t1\t1\t3\t5\tx\t1\tx\t1\tx\t1\t2\t5\tx\t1\t2\t1\t1\t1\t1\t1\t1\t2\t1\t1\tx\t1\t5\t2\tx\t1\tx\t1\tx\t1\tx\t1\tx\t5\t1\t5\tx\t1\tx\t1\tx\t1\t2\t2\tx\t2\tx
x\tx\tx\t1\tx\t1\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\t3\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx
x\t1\tx\t1\tx\t1\t1\t2\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t2\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\t2\t1\t1\tx\t2\tx\t1\tx\t1\tx\t8\tx\t2\tx\t2\tx\t1\t2\t1\tx\t1\tx\t1\tx\t2\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t8\tx\t5\t1\t1\t2\t3\t2\t1\tx\t1\tx\t1\t2\t1\tx\t1\tx\t2\t1\t2\t1\t1\tx\t1\tx\t8\tx
x\t1\tx\t2\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\t2\tx\t1\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\t2\tx\tx\tx
x\t1\t1\t1\tx\t1\tx\t1\tx\t2\t1\t1\t1\t1\t2\t1\tx\t1\tx\t1\t1\t1\tx\t3\t2\t1\tx\t1\t1\t1\tx\t1\t2\t1\tx\t1\t1\t1\t2\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\tx\t3\t3\t1\t1\t2\t1\t3\t1\t1\t2\t1\t3\t2\t1\t1\t1\t3\t1\t1\tx\t3\t1\t1\t1\t1\t1\t2\tx\t3\tx
x\t2\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t2\tx\t2\tx\t1\t1\t1\t1\t1\tx\t3\t1\t2\tx\t3\tx\t1\t1\t1\tx\t2\t1\t1\tx\t1\tx\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\tx\t3\t2\t2\t2\t2\t1\t2\t1\t1\tx\t2\tx\t1\t1\t2\t1\t1\tx\t2\tx\t1\t2\t1\t1\t2\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\t1\tx\t1\tx\t2\tx\t1\t1\t2\t1\t2\tx
x\t1\tx\t2\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t5\tx\t5\tx\t1\tx\tx\tx\t5\tx\t3\tx\t2\tx\tx\tx\tx\tx\t2\tx
x\t1\tx\t1\t2\t1\tx\t1\t1\t2\t1\t1\tx\t1\t1\t1\tx\t1\t1\t8\tx\t1\t1\t1\tx\t1\t5\t2\t1\t1\t1\t2\t2\t1\tx\t1\t1\t1\t2\t2\t1\t1\t1\t1\tx\t1\tx\t5\t1\t1\t1\t1\tx\t2\t1\t2\tx\t1\tx\t5\t5\t2\t5\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t5\tx\t1\tx\t1\tx\t1\tx\t1\t5\t1\tx\t3\tx\t1\t3\t1\t5\t1\t1\t1\tx\t2\tx
x\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\t2\tx\t1\tx\t1\t1\t2\tx\t1\t1\t1\t1\t1\tx\t1\t2\t1\t1\t1\t1\t1\tx\t1\t1\t2\t2\t1\tx\t1\t1\t2\t1\t1\t1\t1\tx\t1\t1\t1\t2\t1\tx\t8\tx\t1\t1\t5\t1\t1\t1\t1\t1\t1\t2\t1\tx\t2\tx\t2\tx\t1\t3\t1\t1\t1\tx\t2\tx\t2\t1\t2\t2\t3\t1\t1\t1\t1\t2\t1\tx\t8\tx\t1\t2\t1\tx\t5\t1\t1\tx\t5\t1\t1\tx\t1\tx\t1\t1\t2\tx
x\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\t2\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\t2\tx\tx\tx
x\t1\tx\t1\tx\t1\tx\t1\t1\t2\t2\t2\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t2\tx\t1\t1\t2\tx\t1\tx\t1\t2\t1\t2\t2\tx\t1\t1\t2\t1\t1\tx\t1\tx\t1\tx\t2\tx\t2\tx\t1\tx\t1\t1\t1\tx\t1\t5\t1\t1\t1\t2\t1\tx\t1\t1\t1\tx\t2\tx\t2\tx\t3\t2\t2\tx\t1\tx\t3\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t2\t1\t1\t1\tx\t3\t1\t3\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\t2\tx\t2\tx\t3\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t5\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx
x\t2\t1\t1\tx\t1\t2\t1\tx\t2\t1\t1\tx\t2\t1\t1\t3\t1\t2\t1\tx\t1\t1\t1\tx\t1\tx\t2\t2\t1\t2\t2\t1\t1\tx\t2\tx\t2\tx\t1\t1\t1\tx\t2\t1\t1\t5\t3\t1\t1\t3\t1\tx\t2\tx\t1\tx\t1\tx\t1\t1\t5\t2\t1\t1\t8\tx\t1\t1\t1\t1\t1\tx\t3\t1\t3\tx\t5\tx\t1\tx\t2\tx\t1\t3\t1\t2\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t2\tx
x\t2\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t2\tx\t1\tx\tx\tx
x\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\t2\tx\t2\tx\t1\t1\t2\tx\t1\tx\t1\tx\t1\t1\t1\tx\t3\tx\t2\t1\t2\tx\t1\tx\t1\t1\t1\tx\t1\t1\t2\t1\t1\tx\t1\t2\t3\tx\t1\tx\t1\tx\t1\tx\t1\tx\t3\tx\t1\tx\t2\t1\t5\tx\t2\tx\t1\t5\t1\t1\t1\tx\t1\t2\t5\t1\t1\t1\t1\tx\t1\t2\t2\tx\t1\tx\t2\tx\t2\t3\t1\tx\t1\tx\t5\tx\t1\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t5\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\t3\tx
x\t8\tx\t1\t1\t1\tx\t8\t1\t1\tx\t2\tx\t1\tx\t1\t1\t1\tx\t2\t1\t1\tx\t3\t2\t1\tx\t2\tx\t2\t2\t3\t3\t1\t1\t1\tx\t2\tx\t2\tx\t1\tx\t2\t2\t1\tx\t1\tx\t1\t1\t2\tx\t1\t2\t1\tx\t1\t2\t1\t5\t1\tx\t2\t1\t5\t1\t1\t1\t1\tx\t1\tx\t5\t1\t2\t2\t2\t1\t1\t3\t1\tx\t2\t1\t1\tx\t2\tx\t1\t1\t1\t2\t3\tx\t1\t1\t2\t5\t1\tx
x\tx\tx\t1\tx\t3\tx\tx\tx\tx\tx\t2\tx\t1\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t3\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t5\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\t3\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx
x\t2\t1\t1\tx\t1\t1\t1\tx\t2\tx\t1\t5\t2\tx\t1\tx\t1\tx\t1\tx\t5\t1\t5\tx\t1\t1\t3\tx\t1\t1\t2\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t2\t1\t1\tx\t1\t1\t2\tx\t1\tx\t2\tx\t1\tx\t1\tx\t1\tx\t2\tx\t1\tx\t1\t1\t3\tx\t2\t2\t5\t1\t1\t1\t1\tx\t1\tx\t1\t2\t1\t2\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\t2\t1\t1\t5\t5\t5\tx
x\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\t5\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\t5\tx\t2\tx\tx\tx\t3\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t2\tx\t2\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx
x\t2\t1\t1\tx\t5\t2\t1\t1\t1\t3\t5\tx\t1\t1\t3\t1\t1\tx\t1\t2\t8\tx\t1\tx\t1\tx\t3\t3\t2\t1\t1\t1\t5\t1\t1\tx\t1\t2\t1\t1\t1\t1\t5\tx\t1\t1\t1\tx\t2\t1\t2\t1\t1\tx\t8\tx\t1\tx\t5\tx\t1\tx\t2\t1\t5\tx\t1\t1\t1\tx\t2\tx\t1\t2\t1\t1\t2\t1\t2\t1\t8\tx\t1\t2\t2\t1\t2\t5\t1\tx\t5\t1\t1\tx\t1\t5\t1\tx\t1\tx
x\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t5\tx\t3\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t5\tx\t3\tx\tx\tx\t1\tx\tx\tx
x\t5\tx\t1\t5\t1\t1\t2\tx\t5\tx\t1\tx\t1\t1\t3\tx\t1\t1\t2\tx\t1\tx\t3\tx\t1\tx\t1\t2\t1\t1\t1\t1\t1\tx\t8\tx\t1\t1\t1\tx\t2\tx\t2\tx\t3\t1\t1\tx\t2\t1\t5\t2\t3\tx\t1\tx\t2\t1\t1\tx\t1\t1\t2\t1\t2\t5\t2\t1\t1\tx\t1\t1\t1\tx\t2\t3\t2\tx\t1\t5\t1\tx\t1\t1\t2\t3\t2\tx\t1\tx\t1\tx\t1\t1\t5\tx\t1\tx\t1\tx
x\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t5\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t5\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t2\tx\t2\tx\tx\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\t1\tx\t1\tx
x\t2\tx\t1\tx\t2\t3\t1\tx\t1\tx\t1\t1\t1\tx\t2\t1\t1\tx\t2\t1\t1\t5\t3\t3\t2\t2\t1\t1\t5\t1\t2\tx\t1\t3\t1\t2\t3\tx\t1\tx\t1\t3\t1\t1\t2\t2\t1\tx\t1\tx\t1\t3\t1\t1\t2\t1\t1\t1\t1\t5\t1\t3\t2\tx\t1\t2\t1\t2\t1\tx\t1\t1\t3\t1\t1\tx\t1\tx\t1\t5\t1\tx\t2\t1\t2\t2\t1\tx\t1\t2\t2\t1\t5\t2\t1\t5\t1\t1\t1\tx
x\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t3\tx\t1\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t1\tx
x\t1\tx\t3\t2\t1\t1\t2\t3\t1\t2\t1\t1\t8\tx\t1\t1\t5\tx\t5\tx\t1\t2\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\t3\t1\tx\t1\tx\t2\t1\t3\tx\t1\tx\t1\t5\t2\t1\t1\t2\t1\tx\t1\tx\t1\tx\t1\t2\t5\t1\t5\t5\t2\tx\t2\t1\t2\tx\t2\t1\t2\t1\t5\tx\t5\t1\t1\t1\t1\t2\t3\t1\t1\t5\t3\tx\t1\t1\t1\tx\t2\tx\t1\t1\t2\tx\t1\t2\t1\tx
x\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t5\tx\t3\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t5\tx\tx\tx\tx\tx\t5\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx
x\t2\tx\t1\tx\t1\t1\t5\t2\t1\tx\t1\tx\t1\t1\t2\t1\t1\t1\t5\t1\t2\tx\t2\tx\t2\t1\t1\tx\t2\t1\t1\t2\t2\tx\t1\tx\t2\t2\t1\t2\t5\tx\t2\tx\t1\tx\t1\tx\t2\t1\t2\tx\t1\tx\t1\t1\t5\t1\t3\t1\t1\t1\t2\tx\t2\t1\t1\tx\t2\tx\t3\t1\t1\t1\t2\tx\t2\tx\t2\tx\t1\tx\t2\t2\t1\tx\t1\tx\t2\t5\t5\t2\t1\t1\t2\tx\t8\tx\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\t3\tx\tx\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\t3\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx
x\t1\tx\t1\t2\t2\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t2\t2\tx\t1\tx\t1\tx\t1\t2\t1\tx\t1\tx\t1\t1\t1\tx\t1\t2\t5\tx\t1\t2\t1\tx\t2\t2\t1\t1\t2\t1\t1\tx\t1\t1\t1\tx\t1\t3\t5\t2\t2\t1\t3\t1\t1\tx\t1\t5\t1\tx\t1\t1\t1\tx\t1\t1\t1\t2\t1\tx\t1\tx\t2\t2\t5\t1\t1\tx\t1\t1\t2\tx\t1\t1\t1\tx\t5\tx\t1\t1\t1\tx\t2\tx
x\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t3\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\t3\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx
x\t2\tx\t1\tx\t1\t2\t1\tx\t1\t1\t1\t3\t1\t2\t1\tx\t2\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t5\tx\t2\t5\t2\t2\t1\t2\t1\t2\t1\tx\t2\t1\t5\tx\t1\tx\t2\tx\t1\t1\t1\tx\t1\t1\t5\tx\t2\tx\t1\t1\t1\t1\t2\t5\t1\tx\t2\tx\t8\tx\t5\t3\t1\t2\t1\t2\t1\tx\t1\t1\t3\tx\t1\t5\t1\tx\t1\t5\t1\t2\t3\t2\t5\tx\t1\t1\t1\t1\t5\tx
x\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\t1\tx\t2\tx\t5\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx\t2\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx
x\t2\tx\t1\tx\t1\tx\t1\tx\t5\t2\t1\t1\t8\tx\t3\t1\t2\t1\t2\t2\t1\t1\t2\t2\t1\tx\t3\tx\t5\tx\t1\t2\t2\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t5\t2\t2\t1\tx\t8\tx\t1\tx\t1\t1\t1\t1\t2\tx\t1\tx\t2\t1\t5\tx\t3\t1\t1\t1\t5\t1\t1\tx\t1\tx\t1\tx\t2\t1\t1\tx\t1\t1\t1\t1\t5\tx\t1\t1\t1\t1\t1\t2\t2\tx\t1\t1\t2\tx\t1\tx
x\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t5\tx\t2\tx\tx\tx\tx\tx\t3\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\t3\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\t1\tx
x\t1\tx\t2\t2\t1\tx\t1\t1\t1\tx\t5\t1\t1\tx\t2\tx\t1\tx\t1\tx\t3\tx\t1\tx\t2\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\tx\t2\t2\t1\t3\t2\tx\t1\t2\t2\t1\t1\t2\t1\tx\t1\tx\t1\tx\t2\t1\t1\t2\t2\t2\t2\t1\t1\tx\t2\tx\t1\tx\t2\t5\t1\tx\t5\t3\t5\tx\t2\t1\t1\t5\t1\tx\t3\tx\t2\tx\t1\tx\t1\t1\t5\t3\t1\t2\t1\tx
x\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t2\tx\t2\tx\t1\tx\tx\tx\t2\tx\t1\tx\t2\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\t5\tx\tx\tx\t2\tx\t1\tx\t3\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\t1\tx
x\t1\t1\t3\tx\t2\tx\t1\tx\t2\t1\t1\t2\t1\t2\t1\t1\t2\t1\t2\tx\t1\tx\t2\t2\t1\tx\t1\tx\t2\t3\t1\t1\t2\t2\t2\t1\t1\tx\t1\t3\t1\tx\t1\t1\t1\tx\t2\tx\t3\tx\t1\t3\t1\t1\t1\tx\t2\tx\t1\t2\t1\tx\t1\tx\t1\tx\t2\t5\t1\t1\t5\tx\t1\tx\t1\t2\t1\tx\t1\t3\t2\t2\t1\tx\t1\t2\t3\t1\t1\t2\t1\t2\t2\t1\t3\t5\t1\tx\t1\tx
x\t1\tx\tx\tx\t1\tx\t1\tx\t1\tx\t1\tx\tx\tx\t3\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\t2\t1\t5\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\t1\tx\tx\tx\t3\tx\t1\tx\t2\tx\tx\tx\tx\tx\t2\tx\t2\tx\t5\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\t5\tx\tx\t1\t2\t1\tx\tx\t3\tx\t1\tx\tx\tx\tx\tx
x\t1\tx\t3\tx\t5\t2\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t5\tx\t2\t1\t1\tx\t2\t2\t1\tx\t1\t1\t1\t2\t1\tx\t1\t5\t2\t2\t3\t1\t2\t1\t2\t1\t5\t1\t3\tx\t1\tx\t2\tx\t1\tx\t2\tx\t3\t5\t2\t1\t1\t2\t1\t1\t2\tx\t1\t1\t1\tx\t1\t1\t1\tx\t2\t1\t1\t5\t2\tx\t1\tx\t5\t1\t1\t1\t2\t2\t3\t1\t5\tx\t2\t2\t2\t3\t1\tx
x\t5\tx\t1\tx\tx\tx\t5\tx\t5\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t3\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t3\tx\t2\tx\tx\tx\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\t1\t5\t1\t1\t2\t1\t1\t2\t2\tx\t2\t1\t1\t1\t2\tx\t2\t1\t1\tx\t5\t1\t8\tx\t5\tx\t1\t2\t1\t1\t1\t2\t2\tx\t1\tx\t1\t1\t5\tx\t5\tx\t1\tx\t2\tx\t2\t3\t2\t2\t1\tx\t3\t1\t2\tx\t1\t3\t1\tx\t1\t1\t1\tx\t3\tx\t5\tx\t8\tx\t2\t2\t1\t1\t5\tx\t1\t2\t1\tx\t3\tx\t1\tx\t8\tx\t1\t3\t1\t1\t1\t1\t2\t2\t2\t1\t1\tx\t2\tx
x\t1\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t1\tx\tx\tx\tx\tx\t2\tx\tx\tx\tx\tx\t1\tx\tx\tx\t2\tx\tx\tx\t1\tx\t1\tx\t2\tx\t3\tx\t2\tx\tx\tx\t1\tx\t1\tx\tx\tx\t2\tx\t1\tx\tx\tx\t3\tx\t1\tx\t1\tx\t1\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx\t1\tx\t2\tx\t5\tx\t1\tx\t1\tx\tx\tx\t5\tx\tx\tx\t1\tx\t1\tx
x\t1\t2\t1\t1\t2\tx\t2\t1\t1\t1\t1\tx\t5\t1\t3\t2\t1\tx\t3\tx\t2\t1\t1\t1\t1\t2\t1\t2\t2\t2\t2\t2\t1\t2\t2\tx\t2\t1\t5\t3\t1\tx\t2\tx\t5\t1\t1\tx\t1\t1\t2\tx\t1\tx\t1\t2\t2\tx\t1\t1\t1\t2\t1\t1\t1\t1\t3\t1\t5\tx\t1\t2\t1\t1\t1\t1\t5\tx\t1\tx\t1\tx\t5\t2\t2\tx\t2\tx\t5\tx\t3\t1\t1\tx\t1\t1\t1\t1\t1\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
`;

const chestsAsObj = [
  {"x":19,"y":1,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":49,"y":1,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":89,"y":1,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":61,"y":3,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":27,"y":5,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":73,"y":7,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":1,"y":9,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":53,"y":13,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":89,"y":13,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":23,"y":15,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":88,"y":16,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":49,"y":21,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":73,"y":23,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":11,"y":27,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":3,"y":31,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":55,"y":31,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":39,"y":35,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":79,"y":39,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":97,"y":39,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":17,"y":41,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":25,"y":43,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":29,"y":43,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":53,"y":45,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":3,"y":49,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":27,"y":53,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":47,"y":55,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":73,"y":55,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":99,"y":55,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":19,"y":61,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":43,"y":63,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":81,"y":63,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":65,"y":67,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":1,"y":71,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":7,"y":71,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":21,"y":75,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":55,"y":75,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":81,"y":75,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":35,"y":77,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":13,"y":81,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":97,"y":83,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":69,"y":87,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":13,"y":89,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":49,"y":89,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":23,"y":97,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":69,"y":97,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
  {"x":85,"y":97,"bonus":2,"amount":8,"html":"Вжух! Случайная ячейка открыта!"},
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
  return {map, width, height, chests, opened: [], scores: [], flags: {}};
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



const colors = ['#ff0044', '#68386c', '#b55088', '#f6757a', '#c0cbdc', '#8b9bb4', '#5a6988', '#3a4466', '#262b44', '#193c3e', '#124e89', '#0099db', '#2ce8f5', '#feae34', '#fee761', '#63c74d', '#3e8948', '#265c42', '#ead4aa', '#e4a672', '#b86f50', '#f77622', '#733e39', '#be4a2f', '#d77643', '#a22633', '#e43b44'];
const commands = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
async function runAll() {
  let tlCommandId = commands.shift();
    console.log('команда')
    await postData(`/game/timeline/${tlCommandId}`, {})
      .then(resp => {
        runTLAnimation(resp, tlCommandId);
      });
}



async function runTLAnimation(response, tlCommandId) {
  // Парсим timestamp'ы
  Object.assign(scene, convertMap(mapAsString));
  for (const $row of scene.$cells) {
    for (const $cell of $row) {
      $cell.style.background = null;
      $cell.style.color = null;
    }
  }
  updateMap();
  const studentColors = {};
  let lastUsedColor = 0;
  response.forEach(obj => obj.tss = new Date(obj.ts).getTime());
  scene.$header.innerHTML = `<div>Команда ${tlCommandId}</div>`;
  let timeOut = new URL(window.location).searchParams.get('ms');
  let realtime = false;
  let timePeriod;
  const destAnimationDurMs = (new URL(window.location).searchParams.get('dur'))*1000 || 20000;
  if (timeOut === undefined || timeOut === null) {
    timeOut = Math.max(4, 1000 / response.length);
  } else if (timeOut === '0') {
    realtime = true;
    timePeriod = response[response.length - 1].tss - response[0].tss;
  }
  let prevSleepStart = response[0].tss;
  for (let i = 0; i < response.length; i++) {
    const student_id = response[i].student_id;
    if (studentColors[student_id] === undefined) {
      studentColors[student_id] = colors[lastUsedColor];
      lastUsedColor += 1;
    }
    const useColor = studentColors[student_id];

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
    scene.$cells[rown][coln].style.background = useColor;
    scene.$cells[rown][coln].style.color = useColor;
    if (timeToSleep >= 1) {
      await sleep(timeToSleep);
      updateMap();
    }
  }
  updateMap();
  scene.$header.innerHTML = `<div>Завершено. Команда ${tlCommandId}</div>`;
  // await sleep(300);
  // alert(tlCommandId);
  await sleep(3000);
  await runAll();
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
        if (cellValue !== 'o') {
          // $cell.className = `s${cellValue}`;
          $cell.className = cellValue === 'x' ? `sx` : `s1`;
        }
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
  // renderHeader();
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
  // runAll();
  setTimeout(runAll, 3000);
  // if (!DEBUG) {
  //   fetchInitialData();
  // } else {
  //   const response = {
  //     opened: [],
  //     events: [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
  //     flags: [],
  //     myFlag: null,
  //     chests: [],
  //   };
  //   refreshData(response);
  //   updateMap();
  //   renderHeader();
  // }
  // prepareWebsockets();
  // setInterval(() => fetchInitialData(), 60 * 1000);
}


function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    document.documentElement.requestFullscreen();
  }
}

window.addEventListener('load', init);


// http://127.0.0.1:8080/game?ms=0&dur=2
