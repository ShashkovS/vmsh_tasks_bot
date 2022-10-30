const CELL_SIZE_IN_REM = 3;
const MODAL_WIDTH_IN_CELLS = 5;
const MODAL_HEIGHT_IN_CELLS = 3;
const FOG_OF_WAR = 15;


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
x\t1\t1\t1\tx\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\tx\t2\tx\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t4\t4\tx
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
x\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t1\t1\t1\t5\t1\t1\t5\t2\t2\t2\t2\t2\tx\t1\t3\t1\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\t5\tx\tx\t5\tx\tx\tx\tx\tx\tx\tx\t1\t1\t1\t5\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx
x\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t6\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx\tx
x\t1\t3\t1\t3\t1\t3\t1\t3\t1\t3\t1\tx\tx\tx\tx\tx\tx\t1\t1\tx\t1\t3\t1\t3\t1\t3\t1\tx\t9\t3\t3\t3\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t2\tx\tx\tx
x\t1\t3\t1\t3\t1\t3\t1\t3\t1\t3\t1\t1\t1\t1\t3\t3\tx\t1\t1\tx\t1\t3\t1\t3\t1\t3\t1\tx\tx\tx\tx\t6\tx\t4\tx\tx\tx\tx\tx\t1\t1\t1\t1\t1\t1\t1\t2\tx\tx\t8\tx
x\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t3\t3\tx\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t1\t5\t1\t1\t1\tx\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t1\t2\tx\tx\t1\t1\tx
x\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t6\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\t1\t3\t1\tx\t2\t2\t2\t2\t2\tx\t1\t1\t1\t1\t1\t2\t5\tx\t1\t1\t1\tx
x\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t5\t1\t1\t1\tx\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\t1\t1\t5\t1\t3\t1\tx\tx\tx\tx\tx\t4\tx\t1\t1\t1\t1\t2\t5\t5\to\t1\t1\t3\tx
x\t1\t1\t1\t1\t1\t1\tx\t1\t3\t1\tx\t1\t1\t1\tx\t1\tx\t1\tx\t1\tx\t1\t3\t3\t1\t3\t3\t1\tx\t1\t1\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t1\t2\tx\tx\to\to\t1\t3\t5\tx
x\t3\t1\t1\t1\t1\t1\tx\t3\t5\t3\tx\t1\t1\t2\tx\t1\tx\t1\tx\t1\tx\t1\t1\t1\t1\t1\t1\t1\tx\t1\t3\t1\tx\t1\t1\t1\t1\t1\tx\t1\t1\t2\tx\tx\t1\t1\t1\t3\t5\t6\tx
x\t5\t3\t1\t1\t1\t1\tx\t1\t3\t1\tx\t1\t2\t4\tx\t1\tx\t1\tx\t1\tx\t1\t3\t3\t1\t3\t3\t1\tx\t1\t3\t1\tx\t1\t1\t1\t1\t1\tx\t1\t2\tx\tx\t1\t1\t1\t3\t5\t6\t7\tx
x\t10\t5\t3\t1\t1\t1\t5\t1\t1\t1\tx\t2\t4\t8\tx\t1\t1\t1\tx\t1\t4\t1\t1\t1\t1\t1\t1\t1\tx\t1\t1\t1\t5\t1\t1\t1\t1\t1\t5\t2\tx\tx\t8\t1\t1\t3\t5\t6\t7\t10\tx
x\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx\tx
`;

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
  opened: [],
  scores: {}, // scores: {1:1}

};


function showPopup(x, y, html, button1, buttonTitle1, buttonOnclick1, button2 = undefined, buttonTitle2 = undefined, buttonOnclick2 = undefined) {
  const curRem = parseFloat(getComputedStyle(document.documentElement).fontSize);
  const halfModalWidth = CELL_SIZE_IN_REM * MODAL_WIDTH_IN_CELLS * curRem / 2;
  const halfModalHeight = CELL_SIZE_IN_REM * MODAL_HEIGHT_IN_CELLS * curRem / 2;
  let useTop = y - halfModalHeight - CELL_SIZE_IN_REM * curRem / 2;
  if (useTop < halfModalHeight) {
    useTop = y + halfModalHeight + CELL_SIZE_IN_REM * curRem / 2;
  }

  scene.$modal.style.top = `${useTop}px`;
  scene.$modal.style.left = `${Math.min(Math.max(x, halfModalWidth), window.scrollX + window.innerWidth - halfModalWidth)}px`;

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
  return {map, width, height};
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


function postBuy($cell, amount) {
  postData('/game/buy', {x: $cell.coln, y: $cell.rown, amount})
    .then(resp => {
      console.log(resp);
      $cell.className = 'so';
      const cellID = $cell.rown * scene.width + $cell.coln;
      scene.opened.push(cellID);
      updateMap();
      updateMap();
      renderHeader();
    });
}

function fetchInitialData() {
  scene.$header.innerHTML = `<div><p><span>...⚡</span> — загружаем информацию...</p></div>`;
  postData('/game/me', {})
    .then(resp => {
      console.log(resp);
      scene.opened.push(...resp.opened.map(([x, y]) => y * scene.width + x));
      for (const diff of resp.events) {
        if (diff > 0) {
          scene.scores[diff] = (scene.scores[diff] | 0) + 1;
        } else {
          buy(-diff);
        }
      }
      updateMap();
      renderHeader();
    });
}


function yesClicked($cell, amount) {
  $cell.textContent = "...";
  $cell.onclick = null;
  buy(amount);
  renderHeader();
  hidePopup();
  postBuy($cell, amount);
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
  const centerX = $cell.offsetLeft + $cell.offsetWidth / 2 - document.body.scrollLeft;
  const centerY = $cell.offsetTop + $cell.offsetHeight / 2 - document.body.scrollTop;

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
      showPopup(centerX, centerY, `Не хватает ⚡<br>Решите задачку!`, 'Буду решать!', 'Закрыть окно', () => okClicked($cell));
    } else {
      showPopup(centerX, centerY, `Изучить клетку<br>за ${$cell.textContent}⚡?`, '✅ Да!', 'Да, изучить клетку!', () => yesClicked($cell, amount), '❌ Нет', 'Нет, вернуться назад', () => noClicked($cell));
    }
  } else {
    $cell.classList.add('selected');
    showPopup(centerX, centerY, `Можно изучать<br>только соседние`, 'Ясно', 'Закрыть окно', () => okClicked($cell));
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
        const newCellID = cellID + diff;
        if (distances.get(newCellID) === undefined) {
          distances.set(newCellID, distances.get(cellID) + 1);
          nextLayer.add(newCellID);
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
      const cellID = rown * scene.width + coln;
      const dist = distances.get(cellID);
      const isBorder = rown === 0 || coln === 0 || coln === scene.width - 1 || rown === scene.height - 1;
      if (dist < FOG_OF_WAR || isBorder) {
        $cell.textContent = cellValue;
        $cell.className = `s${cellValue}`;
        if (+cellValue) {
          $cell.onclick = $cell.ondblclick = onCellClick;
        } else {
          $cell.onclick = $cell.ondblclick = null;
        }
        if (!isBorder && FOG_OF_WAR - dist <= 8) {
          $cell.style.opacity = (FOG_OF_WAR - dist) / 8;
        } else {
          $cell.style.opacity = 1;
        }
      } else {
        $cell.textContent = '';
        $cell.className = 'fog';
        $cell.onclick = $cell.ondblclick = null;
      }
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
      const $cell = $tableRow.insertCell();
      $cellsRow.push($cell);
      $cell.coln = coln;
      $cell.rown = rown;
    }
  }
}

function prepareWebsockets() {
  scene.curWebSocket = null;
  function onWebSocketOpen(ev) {
    console.log('Websocket open', ev);
  }
  function onWebSocketMessage(ev) {
    console.log('Message', ev);
  }
  function onWebSocketClose(ev) {
    if (ev.wasClean) {
      console.log('Clean connection end')
    } else {
      console.log('Connection broken')
    }
    scene.curWebSocket = null;
  }
  function createWebSocketConnection() {
    let ws;
    try {
      ws = new WebSocket('ws://' + window.location.host + '/game/ws');
    } catch (err) {
      ws = new WebSocket('wss://' + window.location.host + '/game/ws');
    }
    ws.onopen = onWebSocketOpen;
    ws.onmessage = onWebSocketMessage;
    ws.onclose = onWebSocketClose;
    return ws;
  }
  scene.curWebSocket = createWebSocketConnection();
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
  updateMap();
  fetchInitialData();
  prepareWebsockets();
}

function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    document.documentElement.requestFullscreen();
  }
}
