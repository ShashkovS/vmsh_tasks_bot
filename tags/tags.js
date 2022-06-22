const allTags = {};
const suggestions = ['арифметика', 'взвешивания', 'включения-исключения', 'геометрия', 'графы', 'движение', 'двумя способами', 'делимость', 'деревья', 'десятичная запись', 'дроби', 'замощение', 'игры', 'инвариант', 'клетчатая геометрия', 'количество информации', 'комбинаторика', 'конструкции', 'контрпримеры', 'круги Эйлера', 'логика', 'необычные конструкции', 'неравенство треугольника', 'обратный ход', 'остатки', 'от противного', 'оценка', 'перебор', 'полуинвариант', 'последняя цифра', 'признаки делимости', 'принцип крайнего', 'проценты и части', 'пути Эйлера', 'разложение на множители', 'разрезание', 'раскраска', 'рыцари и лжецы', 'симметрия', 'системы счисления', 'сочетания', 'средние значения', 'суммирование', 'текстовые задачи', 'теория вероятности', 'уравнение', 'часы со стрелками', 'чётность', 'шутки'];
let initialDone = false;
let locked = false;
let socket = null;
const prob_ids_to_send_tags = new Set();
let dbTags = null;
let updateTimeout = null;

fetch('/tag/get_tags', {
    method: 'GET',
    headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
}).then(res => res.json())
    .then(res => {
        dbTags = res;
        createTags();
    });

function initSocket() {
    // socket = new WebSocket("ws://127.0.0.1:8080/tag/ws");
    socket = new WebSocket(`wss://${window.location.hostname}/tag/ws`);
    socket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        const id = data['id'];
        const freshTags = data['tags'];
        const amsifySuggestags = allTags[id];
        const curTags = amsifySuggestags.tagNames.slice();
        locked = true;
        for (let tag of freshTags) {
            if (!curTags.includes(tag)) {
                amsifySuggestags.addTag(tag, animate = true);
            }
        }
        for (let tag of curTags) {
            if (!freshTags.includes(tag)) {
                amsifySuggestags.removeTag(tag);
            }
        }
        locked = false;
        console.log(`[message] Данные получены с сервера: ${event.data}`);
    };
    socket.onclose = function (event) {
        console.log(`[close] Соединение закрыто чисто, код=${event.code} причина=${event.reason}`);
        setTimeout(initSocket, 1000);
    };
    socket.onerror = function (error) {
        console.log(`[error] ${error}`);
    };
}

initSocket();

function sendAllUpdates() {
    if (!initialDone || locked) {
        updateTimeout = setTimeout(sendAllUpdates, 4);
        return
    }
    const tagsToUpdateIterator = prob_ids_to_send_tags.values();
    let nextTag;
    while (nextTag = tagsToUpdateIterator.next().value) {
        socket.send(JSON.stringify({id: nextTag, tags: allTags[nextTag].tagNames}));
        prob_ids_to_send_tags.delete(nextTag); // todo удалять тогда, когда пришёл ответ
    }
    updateTimeout = null;
}

function processTag(i, obj) {
    const jobj = $(obj);
    const id = jobj.attr('id');
    const idP01 = id + '_01';
    if (allTags[idP01] === undefined) {
        jobj.css("display", "block");
        const amsifySuggestags = new AmsifySuggestags(jobj);
        allTags[id] = amsifySuggestags;

        function onChange() {
            if (!initialDone || locked) return;
            console.info('afterAdd', id, amsifySuggestags.tagNames); // Parameter will be value
            // debugger;
            prob_ids_to_send_tags.add(id);
            if (!updateTimeout) updateTimeout = setTimeout(sendAllUpdates, 4);

        }

        amsifySuggestags._settings({
            type: 'amsify',
            afterAdd: onChange,
            afterRemove: onChange,
            printValues: false,
            suggestions,
        });
        amsifySuggestags.defaultLabel = 'Добавьте теги';
        amsifySuggestags._init();
        for (const tag of dbTags[id] || []) {
            amsifySuggestags.addTag(tag, animate = true);
        }
    }
}


function createTags() {
    if (!dbTags || initialDone) return;
    $('.itag').each(processTag);
    $('.ptag').each(processTag);
    initialDone = true;
}

function show_stat() {
    $('.stat').css('display', 'inline');
    createTags();
}

window.onload = show_stat;
