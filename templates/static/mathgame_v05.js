"use strict";

const CELL_SIZE_IN_REM = 3;
const MODAL_WIDTH_IN_CELLS = 5;
const MODAL_HEIGHT_IN_CELLS = 3;
const FOG_OF_WAR = 10;
const FOR_OPACITY_LEN = 10;

const DEBUG = false;

const mapAsString = `
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\t1\t1\t1\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\to\to\to\to\to\to\to\to\to\to\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t7\t7\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx
x\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t3\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\to\to\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\tx\tx\tx\tx\tx\t1\tx\t1\t7\t1\t1\t1\tx
x\t1\t1\t1\tx\tx\tx\t1\t1\t1\t1\t3\t4\t3\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t1\t9\t1\t1\tx\t1\t7\t1\t1\t1\tx
x\t1\t1\tx\t1\tx\t10\tx\t1\t1\t1\t1\tx\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t7\t1\t1\t1\tx
x\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\tx\tx\t1\t1\t1\tx\t5\t5\t5\t5\t5\tx\t5\t5\t5\t5\t5\t5\tx\t4\tx\tx\tx\tx\tx\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t7\t2\t2\t2\tx
x\t1\t1\t1\tx\tx\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\tx\t1\tx\t1\t10\t.\tx\t1\t1\tx\t1\t2\t1\t2\t1\tx\t1\t7\t1\t1\t1\tx
x\t1\t1\tx\t9\tx\t1\tx\t1\t1\t1\t1\tx\t1\t1\t1\t1\tx\t1\t5\t5\t5\t5\tx\t1\t5\t5\t5\t5\t5\tx\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t1\t2\t1\t1\tx\t1\t7\t2\t2\t2\tx
x\t1\tx\t1\t1\tx\t1\t1\tx\t1\t1\tx\tx\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t2\t1\t2\t1\t8\t1\t7\t1\t1\t1\tx
x\t1\t1\t1\tx\tx\tx\t1\t1\t1\tx\t1\tx\t8\tx\t1\t1\tx\t1\t2\t1\t2\t1\tx\tx\tx\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t7\t2\t2\t2\tx
x\t1\t1\t1\t1\t6\t1\t1\t1\tx\t1\t1\tx\t1\t1\tx\t1\tx\t1\t2\t1\t2\t1\t1\t8\t1\tx\tx\tx\t5\tx\t1\t1\t1\t1\t7\t7\t7\t1\t1\t1\t1\t1\t1\t1\t1\t1\t7\t1\t1\t1\tx
x\t1\t1\t1\t1\t6\t1\t1\t1\t1\t1\tx\tx\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx
x\t1\t1\t1\t1\t6\t1\t1\t1\t1\t1\t6\t6\t6\t1\t1\t1\t5\t1\t1\t1\t1\tx\tx\tx\tx\tx\t1\t1\t1\t3\t1\t1\t1\t1\tx\tx\tx\t1\t1\t1\t3\t1\t1\t1\t1\tx\tx\tx\t1\t1\tx
x\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\t7\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx
x\t1\t1\t1\tx\t1\t1\t1\t1\t5\t1\t1\t1\t4\t1\t1\t1\t5\t1\t1\t1\t1\tx\t7\t7\t1\t1\t1\t1\tx\tx\tx\t1\t1\t1\t1\tx\t1\t1\t1\tx\tx\tx\t1\t1\t1\t1\tx\t1\t1\t1\tx
x\t1\t7\t1\tx\t1\t1\t2\t1\t3\t1\t4\t1\t2\t1\t4\t1\t3\t1\t1\t1\t7\tx\t7\t7\t7\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t3\t1\t1\tx\t1\tx\t1\tx\t1\t1\t1\t3\t1\t1\t1\tx
x\t1\t1\t1\tx\t10\t1\t4\t1\t1\t1\t6\t1\t1\t1\t5\t1\t1\t1\t1\t7\t7\t7\t7\t7\t7\t7\t1\t1\t1\tx\t1\t1\t1\t1\t1\t3\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t3\t1\t1\t1\tx
x\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t7\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx
x\t1\t1\t1\t6\t1\t1\t1\t1\t1\t1\t3\t1\t1\t7\t1\t1\t3\t1\t1\t1\t1\t7\t7\t7\t1\t1\t1\t1\t1\t1\t7\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\t1\t1\t1\t1\t7\t1\t1\t1\t1\tx
x\t1\t1\tx\tx\tx\t1\t1\t1\t1\t1\t5\t1\t1\t6\t1\t1\t5\t1\t1\t1\t1\t1\t7\t1\t1\t1\t1\t1\t1\t1\t6\t1\t1\t1\t1\t2\t1\t1\t1\t2\t2\t2\t1\t1\t1\t6\t1\t1\t2\t1\tx
x\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t7\t1\t1\t5\t1\t1\t7\t1\t1\t2\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t5\t1\t1\t1\t2\t2\t2\t1\t1\t1\t2\t1\t1\t1\t1\t5\t1\t2\t2\t2\tx
x\t2\t2\t2\tx\t1\t2\t2\t2\t1\t1\tx\t1\t1\t4\t1\t1\tx\t1\t1\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t4\t1\t1\t1\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t1\t4\t1\t1\t2\t1\tx
x\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t10\tx\t1\t3\t1\tx\t9\tx\t1\t2\t1\t2\t1\t1\t1\t1\t1\t1\t1\t1\t3\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t3\t1\t1\t1\t1\tx
x\t2\t2\t2\tx\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t2\t1\t1\tx\t1\t1\t1\tx\tx\tx\tx\tx\t1\tx\t1\t2\t1\tx\t1\t1\tx
x\t1\t1\t1\tx\t7\t5\t3\t1\tx\t1\t1\t1\t1\tx\t1\t1\t1\t1\tx\t1\t1\t1\tx\tx\t1\t1\t1\tx\tx\t1\t1\t1\tx\t1\tx\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\tx
x\t2\t2\t2\tx\t1\t1\t1\t1\tx\t1\t1\t1\t2\t1\t2\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\tx\t1\t8\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\tx
x\t1\t1\t1\tx\t1\t1\t2\t1\tx\t1\t1\t1\t1\t2\t1\t1\t1\t1\tx\t1\t2\t1\tx\t1\t1\tx\t1\t1\tx\t1\t1\tx\t1\t1\t1\tx\t1\t2\t1\tx\t1\t1\t1\tx\tx\tx\tx\tx\t1\t1\tx
x\t1\t1\t1\tx\t1\t1\t3\t1\t1\tx\t1\t1\t2\t1\t2\t1\t1\tx\t1\t1\t3\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\tx\tx\t6\tx\tx\t1\t3\t1\tx\t1\t1\t1\tx\t1\t8\t1\tx\t1\t1\tx
x\t1\t1\tx\tx\tx\t1\t4\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t4\t1\tx\t1\t2\t1\t2\t1\tx\t1\t1\tx\t1\t1\t1\tx\t1\t4\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\tx
x\t1\t1\t1\t1\t1\t1\t5\t1\t1\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t5\t1\t1\t1\t1\t2\t1\t1\t4\t4\t4\t4\t1\t1\t1\t1\t1\t5\t1\t1\t1\t1\t6\t1\t1\t1\t1\t1\t1\t1\tx
x\t7\t7\t7\t1\t1\t1\t6\t1\t1\t1\t1\t1\tx\t1\tx\t1\t1\t1\t1\t1\t6\t1\t1\t1\t2\t1\t2\t1\t4\t4\t4\t4\t1\t1\t1\t1\t1\t6\t1\t1\t1\t6\t6\t6\t1\t1\t1\t7\t7\t7\tx
x\t7\t7\t7\t1\t1\t1\t7\t1\t1\t1\t1\t1\t6\t6\t6\t1\t1\t1\t1\t1\t7\t1\t1\t1\t1\t1\t1\t1\t4\t4\t4\t4\t1\t1\t1\t1\t1\t7\t1\t1\t1\t1\t6\t1\t1\t1\t1\t7\t7\t7\tx
x\tx\t7\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t7\tx\tx
x\t7\t7\t7\t2\t2\t2\t2\t2\t2\t6\t2\t2\t2\t3\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\t6\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t7\t7\t7\tx
x\t7\t7\t7\t2\t2\t2\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\tx\tx\tx\t1\t1\t1\t1\tx\t1\t7\t7\t7\tx
x\t2\t2\t2\t2\tx\t2\t2\t2\t2\tx\t2\t2\tx\t2\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\t2\tx\t2\t2\t2\t2\t2\tx\tx\tx\t1\t1\tx\t1\tx\t1\tx\t1\t1\tx\tx\tx\t1\t1\t1\tx
x\t2\t2\t2\tx\t2\tx\t2\t2\tx\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\t2\t2\tx\t2\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\tx\t1\tx\t10\tx\t1\t1\tx
x\t2\t2\t2\tx\t2\t2\t2\tx\t2\tx\t2\tx\t2\tx\t2\t2\tx\tx\tx\t2\t2\tx\tx\tx\t2\tx\t2\tx\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t5\t5\t5\t1\t1\t1\t1\tx\t1\t1\t1\t1\tx
x\t2\t2\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\t2\t2\t2\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
x\t2\t2\t2\t2\tx\t2\t2\tx\t2\tx\t2\t2\tx\t2\t2\tx\t2\tx\t2\tx\t2\tx\t2\tx\t2\t2\tx\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx
x\t2\t7\t2\t2\t6\t2\t2\t2\t3\t2\t2\t2\t6\t2\t2\t2\t2\t3\t2\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\t2\t7\t2\tx\t1\t1\tx\t1\t1\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\tx\t1\tx
x\t7\t7\t7\t2\t6\t2\t2\t2\t2\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\t2\t2\t2\t6\t2\t2\t2\t2\t2\t2\t7\t7\t7\tx\t1\tx\tx\t1\t1\t7\t10\t7\t1\tx\t1\tx\t1\t1\t1\tx\t1\tx
x\tx\t7\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t7\tx\tx\t1\t1\tx\t1\t1\t7\t7\t7\tx\tx\t1\tx\t1\t1\t1\tx\t1\tx
x\t7\t7\t7\t1\t1\t6\t1\t1\t1\t1\t1\t1\t1\t6\t6\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t7\t7\t7\tx\t1\t1\tx\t1\t1\t1\t1\tx\tx\t1\t1\tx\tx\tx\tx\tx\t1\tx
x\t1\t7\t1\t1\t1\t6\t1\t1\t1\t1\t1\t1\t1\t6\t6\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t7\t1\tx\t1\t1\tx\t1\t1\t1\tx\tx\t1\t1\t7\t8\t7\t1\tx\tx\t1\tx
x\t1\tx\t1\t1\t1\tx\t1\t1\tx\tx\t1\t1\t1\tx\tx\t1\t1\tx\tx\tx\t1\tx\t1\t1\tx\t1\t1\t2\t2\t2\t2\t2\tx\t1\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t7\t1\tx\tx\t1\t1\tx
x\t1\tx\tx\t1\tx\tx\t1\tx\t1\t1\tx\t1\tx\t6\t8\tx\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t1\t2\t3\t3\t3\t3\tx\t1\t1\tx\t9\t1\t1\tx\t1\t1\t1\t1\t1\tx\tx\t1\t1\t1\tx
x\t1\tx\t1\tx\t1\tx\t1\tx\t1\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t1\t1\tx\t1\t1\tx\t1\t1\t2\t3\t4\t4\t4\tx\t1\tx\tx\tx\t1\t1\tx\t1\t1\t1\t1\tx\tx\t1\t1\t1\t1\tx
x\t1\tx\t1\t8\t1\tx\t1\tx\t1\t1\tx\t1\tx\t1\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\tx\t1\t1\t2\t3\t4\t5\t5\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx
x\t1\tx\t1\t1\t1\tx\t1\t1\tx\tx\t1\t1\t1\tx\tx\t1\t1\tx\t1\t1\t1\tx\t1\t1\t5\t1\t1\t2\t3\t4\t5\t6\tx\t7\t7\t7\t7\t7\t7\t7\t7\t7\t7\t7\t7\t7\t7\t7\t7\t1\tx
x\t1\t3\t3\t3\t3\t3\t1\t1\t6\t6\t1\t1\t1\t1\t1\t1\t1\t6\t1\t1\t1\t6\t1\t1\tx\t1\t1\t2\t3\t4\t5\t6\t7\t6\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx
x\t7\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t7\tx
x\t7\t6\t5\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx\tx\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx\t8\t3\t3\tx\t3\t3\t3\t3\t3\tx\t3\t3\t3\t3\t3\t3\t3\t5\t6\t7\tx
x\t6\t5\t3\t3\t3\t3\t3\t3\t3\t3\tx\t3\tx\t3\t3\tx\t3\tx\t3\tx\t3\tx\t3\tx\tx\tx\tx\tx\t3\tx\tx\t3\t3\tx\t3\tx\tx\tx\t3\tx\t3\t3\t3\t3\t3\t3\t3\t3\t5\t6\tx
x\t5\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx\tx\t8\t3\t3\tx\tx\t3\t3\t3\tx\t3\t3\t3\t3\tx\t3\t3\t3\tx\t3\tx\t3\tx\t3\tx\t8\t3\t3\tx\t3\t3\t3\t3\t3\t3\t3\t3\t3\t5\tx
x\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx\t3\tx\t3\t3\tx\t3\t3\t3\tx\t8\t3\t3\t3\t3\tx\t3\t3\t3\tx\tx\t3\t3\tx\t3\tx\tx\tx\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx
x\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx\t3\t3\tx\t3\t3\t3\t3\tx\t3\t3\t3\t3\t3\t3\tx\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx\t3\t3\t3\tx\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
`;

const chestsAsObj = [
  {x: 46, y: 27, amount: 8,  bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=10116" target="_blank" rel="noopener noreferrer">Финиш</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=10116" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/10116.png" alt="10116"> <div class="play-button"></div></a> <br>Добраться до финиша без левых поворотов не так-то просто!<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 45, y: 44, amount: 8,  bonus: 2, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=11939" target="_blank" rel="noopener noreferrer">Рыцари</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=11939" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/11939.png" alt="11939"> <div class="play-button"></div></a><br> Когда решите, сделайте скриншот и сдайте в бот, это добавит вам баллов :) <br>Это — люто сложная задача. Я сам решал её больше часа. Интересно, хоть кто-нибудь справится?'},
  {x: 45, y: 8,  amount: 8,  bonus: 2, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=11996" target="_blank" rel="noopener noreferrer">Мешок кофе</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=11996" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/11996.png" alt="11996"> <div class="play-button"></div></a><br> Когда решите за 3 взвешивания, сделайте скриншот и сдайте в бот, это добавит вам баллов :) <br>У нас была немного похожая задача, но она была менее амбициозной :)'},
  {x: 40, y: 41, amount: 10, bonus: 2, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=12215" target="_blank" rel="noopener noreferrer">Нить Ариадны</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=12215" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/12215.png" alt="12215"> <div class="play-button"></div></a><br> Когда найдёте решение из 10 батарей, сделайте скриншот и сдайте в бот, это добавит вам баллов :) <br>Найти решение из 10 батарей оооочень непросто :)'},
  {x: 13, y: 9,  amount: 8,  bonus: 2, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=14149" target="_blank" rel="noopener noreferrer">Космический лабиринт</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=14149" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/14149.png" alt="14149"> <div class="play-button"></div></a> <br> Найти решение за 4 хода почти невозможно :)<br> Когда найдёте такое решение, сделайте скриншот и сдайте в бот, это добавит вам баллов :) '},
  {x: 17, y: 22, amount: 9,  bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=14240" target="_blank" rel="noopener noreferrer">Огоньки</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=14240" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/14240.png" alt="14240"> <div class="play-button"></div></a> <br>Это — очень красивая головоломка :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 37, y: 46, amount: 9,  bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=16045" target="_blank" rel="noopener noreferrer">Корабль в тумане</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=16045" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/16045.png" alt="16045"> <div class="play-button"></div></a> <br> По мотивам одной очень известной игры :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 42, y: 3,  amount: 9,  bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=19585" target="_blank" rel="noopener noreferrer">Найди спрятанное</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=19585" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/19585.png" alt="19585"> <div class="play-button"></div></a> <br> Оказывается, всегда достаточно 3 батискафов :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 11, y: 22, amount: 10, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=19664" target="_blank" rel="noopener noreferrer">Узор</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=19664" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/19664.png" alt="19664"> <div class="play-button"></div></a> <br> Игра, кстати, называется «Тантрикс», она родом из Новой Зеландии.<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 15, y: 46, amount: 8,  bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=19696" target="_blank" rel="noopener noreferrer">Набери пятнадцать</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=19696" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/19696.png" alt="19696"> <div class="play-button"></div></a> <br>Эта игра изоморфна... Ой, о чём это я<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 24, y: 10, amount: 8,  bonus: 2, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=19712" target="_blank" rel="noopener noreferrer">Корабль с драконом</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=19712" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/19712.png" alt="19712"> <div class="play-button"></div></a><br> Когда решите, сделайте скриншот и сдайте в бот, это добавит вам баллов :) <br> Английское название головоломки — «rush hour»'},
  {x: 34, y: 6,  amount: 10, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=21271" target="_blank" rel="noopener noreferrer">Олаф строитель</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=21271" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/21271.png" alt="21271"> <div class="play-button"></div></a> <br> Тетрис с приключениями :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 4, y: 7,   amount: 9,  bonus: 2, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=22432" target="_blank" rel="noopener noreferrer">Равновесие</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=22432" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/22432.png" alt="22432"> <div class="play-button"></div></a><br> Когда решите, сделайте скриншот б сдайте в бот, это добавит вам баллов :) <br> Задание немного на физику. Правильные слова — «момент силы» :)'},
  {x: 47, y: 36, amount: 10, bonus: 2, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=22494" target="_blank" rel="noopener noreferrer">Закрась одним цветом</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=22494" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/22494.png" alt="22494"> <div class="play-button"></div></a><br> Когда решите вторую картинку за 5 ходов, сделайте скриншот и сдайте в бот, это добавит вам баллов :) <br> Подготовка этой задачи с иллюстратором была очень увлекательна :)'},
  {x: 34, y: 25, amount: 8,  bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=23675" target="_blank" rel="noopener noreferrer">Голубь</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=23675" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/23675.png" alt="23675"> <div class="play-button"></div></a> <br> Есть известная задача по математике: при каком максимальном соотношении скорости дворника и голубя у последнего есть шанс спастись? Сложная задача.<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 6, y: 4,   amount: 10, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=23995" target="_blank" rel="noopener noreferrer">Доставка пиццы</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=23995" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/23995.png" alt="23995"> <div class="play-button"></div></a> <br>Это вообще про программирование. Но во многом благодаря этой идее у нас вообще есть Интернет.<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 4, y: 48,  amount: 8,  bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=24132" target="_blank" rel="noopener noreferrer">Багаж в аэропорту</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=24132" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/24132.png" alt="24132"> <div class="play-button"></div></a>Это немного про программирование. Называние «задача о максимальном потоке» <br><br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 5, y: 16,  amount: 10, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=24670" target="_blank" rel="noopener noreferrer">Квадраты и пути</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=24670" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/24670.png" alt="24670"> <div class="play-button"></div></a> <br>Вряд ли вы заметите, но эта задача про бублик :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 31, y: 52, amount: 8, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=12086" target="_blank" rel="noopener noreferrer">Границы крепости</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=12086" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/12086.png" alt="12086"> <div class="play-button"></div></a> <br>Проверить правильность решения придётся самостоятельно :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 13, y: 54, amount: 8, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=12239" target="_blank" rel="noopener noreferrer">Кладоискатель</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=12239" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/12239.png" alt="12239"> <div class="play-button"></div></a> <br>Проверить правильность решения придётся самостоятельно :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 37, y: 54, amount: 8, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=21107" target="_blank" rel="noopener noreferrer">Квадраты и пути</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=21107" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/21107.png" alt="21107"> <div class="play-button"></div></a> <br>Не думаю, что вы придумаете минимальное решение :)<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
  {x: 21, y: 55, amount: 8, bonus: 3, html: 'В качестве бонуса вам игра-задачка «<a href="https://olympiads.uchi.ru/preview_card?id=22335" target="_blank" rel="noopener noreferrer">Пути на кубе</a>» с одной из олимпиад на Учи.ру. Кликайте на картинку, что открыть: <br> <a href="https://olympiads.uchi.ru/preview_card?id=22335" target="_blank" rel="noopener noreferrer"><img style="width: 80%; max-width: 80vw;" src="https://shashkovs.ru/ex/22335.png" alt="22335"> <div class="play-button"></div></a> <br>Обожаю эту задачу :) Мне пришлось написать хитрую программу, чтобы эффективно придумывать условия для этой задачи.<br>Сдавать задачу в бот не нужно, баллы вы получите авансом :)'},
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

