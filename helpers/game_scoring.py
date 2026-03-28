# -*- coding: utf-8 -*-
import db_methods as db


def build_group_weight_map():
    weight_map = {}
    for row in db.group.get_all():
        short_code = row.get('short_code')
        if short_code:
            weight = row.get('score_weight')
            if weight is None:
                weight = 1.0
            weight_map[short_code] = float(weight)
    return weight_map


def apply_group_weight(raw_score: int, problem_group_code: str, command_group_code: str, weight_map=None) -> int:
    if raw_score is None:
        return 0
    weight_map = weight_map or build_group_weight_map()
    problem_weight = weight_map.get(problem_group_code)
    command_weight = weight_map.get(command_group_code)
    if not problem_weight or not command_weight:
        return int(raw_score)
    if command_weight <= 0:
        return int(raw_score)
    adjusted = raw_score * (problem_weight / command_weight)
    return int(round(adjusted))
