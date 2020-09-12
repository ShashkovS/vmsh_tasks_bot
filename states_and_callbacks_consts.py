# Важно, чтобы каждый state был уникальной числовой константой, которая больше никогда не меняется
# (так как она сохраняется в БД)
GET_USER_INFO_STATE = 1
GET_TASK_INFO_STATE = 2
SENDING_SOLUTION_STATE = 3

# Важно, чтобы константа была уникальной буков (там хардкод взятия первой буквы)
PROBLEM_SELECTED_CALLBACK = 't'
SHOW_LIST_OF_LISTS_CALLBACK = 'a'
LIST_SELECTED_CALLBACK = 'l'
