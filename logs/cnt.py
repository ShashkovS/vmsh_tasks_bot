from pathlib import Path
import json
from collections import Counter

used_ids = {7350, 7673, 7292, 7978, 8130, 8423, 8782, 5381, 4234, 6735}
chat_ids = {160395642, 472658093, 572492016, 255314690, 7339773413, 5650544201, 6703315848, 8419210572, 422811679, 6649012911}
zoom_names = {'zoom_user_name',
              'Баймиева Юстина',
              'Влад Медвецкий',
              'Георгий Липинский',
              'Дарья Слепых',
              'Н Юстина Баймиева',
              'НЮстина Баймиева',
              'П Баймиева Юстина',
              'П Юстина Баймиева',
              'Принимающий Дарья Слепых',
              'Принимающий Николай Агеев',
              'Э Начоев Даниэль',
              'Юся Баймиева',
              'н Баймиева Юстина',
              'н Юстина Баймиева',
              'п Баймиева Юстина',
              'п Влад Медвецкий',
              'п Начоев Даниэль',
              'принимающая Дарья Слепых',
              'принимающий Дарья Слепых',
              'э Андрюшина Юлия',
              'э Влад Медвецкий',
              }

selected = set()
cnt = Counter()
for file in Path(__file__).parent.glob('*.*'):
    if 'json' not in file.name:
        continue
    for line in file.open():
        obj = json.loads(line)
        need = (
                obj.get('chat_id') in chat_ids
                or obj.get('user_id') in used_ids
                or obj.get('target_user_id') in used_ids
                or obj.get('last_student_id') in used_ids
                or obj.get('last_teacher_id') in used_ids
                or obj.get('student_id') in used_ids
                or obj.get('teacher_id') in used_ids
                or obj.get('zoom_user_name') in zoom_names
                or obj.get('user_id') in used_ids
                or obj.get('user_id') in used_ids
        )
        if need and obj.get('command') != 'reset_state':
            selected.add(line)

selected = [json.loads(line) for line in selected]
selected.sort(key=lambda obj: obj['ts'])
with open('selected.jsonl', 'w') as f:
    for obj in selected:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
print(len(selected))