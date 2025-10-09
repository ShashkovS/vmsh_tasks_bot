# -*- coding: utf-8 -*-
from enum import Enum, unique

from helpers.consts import VERDICT
from helpers.config import logger, config

_VERDICT_PLUS_MINUS = (VERDICT.SOLVED, VERDICT.WRONG_ANSWER)
_VERDICT_PLUS_MINUS_HALF = (VERDICT.SOLVED, VERDICT.VERDICT_PLUS_DIV_2, VERDICT.VERDICT_MINUS)
_VERDICT_PLUS_STEPS = (
    VERDICT.VERDICT_PLUS, VERDICT.VERDICT_PLUS_DOT, VERDICT.VERDICT_PLUS_MINUS, VERDICT.VERDICT_PLUS_DIV_2,
    VERDICT.VERDICT_MINUS_PLUS,
    VERDICT.VERDICT_MINUS_DOT, VERDICT.VERDICT_MINUS
)

VERDICT_MODE: str = ''
RESULT_MODE: str = ''
SAVE_SOL_MODE: str = ''
PREV_PROBLEMS_MODE: str = ''
GAME_MODE: str = ''
REG_MODE: str = ''
RATE_LIMIT_MODE: str = ''
SYNONYMS_MODE: str = ''


@unique
class FEATURES(Enum):
    #### VERDICTS ####
    VERDICT_PLUS_MINUS = _VERDICT_PLUS_MINUS
    VERDICT_PLUS_MINUS_HALF = _VERDICT_PLUS_MINUS_HALF
    VERDICT_PLUS_STEPS = _VERDICT_PLUS_STEPS

    #### RESULTS ####
    RESULT_IMMEDIATELY = 'res_immed'
    RESULT_AFTER = 'res_after'

    #### SAVE SOLS ####
    SAVE_SOL_ON_DRIVE = 'save_on_drive'
    SAVE_SOL_IN_TG_ONLY = 'save_sol_in_tg_only'

    #### PREV PROBLEM SETS ####
    PREV_PROBLEMS_HIDDEN = 'prev_problems_hide'
    PREV_PROBLEMS_PREV = 'prev_problems_prev'
    PREV_PROBLEMS_SHOW_ALL = 'prev_problems_show_all'

    #### GAME ####
    GAME_HIDDEN = 'game_hide'
    GAME_SHOW = 'game_show'

    #### REG ####
    REG_NEEDED = 'reg_needed'
    REG_ANYBODY = 'reg_anybody'

    #### TEST_ANS_RATE_LIMIT ####
    RATE_LIMIT_NONE = 'rate_limit_none'
    RATE_LIMIT_3_AND_6 = 'rate_limit_3_and_6'

    ### SYNONYMS ###
    SYNONYMS_JOIN = 'synonyms_join'
    SYNONYMS_IGNORE = 'synonyms_ignore'



def set_features(config):
    global VERDICT_MODE, RESULT_MODE, SAVE_SOL_MODE, PREV_PROBLEMS_MODE, GAME_MODE, REG_MODE, RATE_LIMIT_MODE, SYNONYMS_MODE
    if config.verdict_mode == 'verdict_plus_minus':
        VERDICT_MODE = FEATURES.VERDICT_PLUS_MINUS
    elif config.verdict_mode == 'verdict_plus_minus_half':
        VERDICT_MODE = FEATURES.VERDICT_PLUS_MINUS_HALF
    elif config.verdict_mode == 'verdict_plus_steps':
        VERDICT_MODE = FEATURES.VERDICT_PLUS_STEPS
    else:
        raise ValueError(
            f'Wrong {config.verdict_mode}. Use verdict_plus_minus/verdict_plus_minus_half/verdict_plus_steps')

    RESULT_MODE = FEATURES(config.result_mode)
    assert RESULT_MODE.value.startswith('res')

    SAVE_SOL_MODE = FEATURES(config.save_sol_mode)
    assert SAVE_SOL_MODE.value.startswith('save')

    PREV_PROBLEMS_MODE = FEATURES(config.prev_problems_mode)
    assert PREV_PROBLEMS_MODE.value.startswith('prev')

    GAME_MODE = FEATURES(config.game_mode)
    assert GAME_MODE.value.startswith('game')

    REG_MODE = FEATURES(config.reg_mode)
    assert REG_MODE.value.startswith('reg')

    RATE_LIMIT_MODE = FEATURES(config.rate_limit)
    assert RATE_LIMIT_MODE.value.startswith('rate')

    SYNONYMS_MODE = FEATURES(config.synonyms_mode)
    assert SYNONYMS_MODE.value.startswith('synonyms')

    logger.info(
        f'{RESULT_MODE=}\n{SAVE_SOL_MODE=}\n{PREV_PROBLEMS_MODE=}\n{GAME_MODE=}\n{REG_MODE=}\n{RATE_LIMIT_MODE=}'
    )


set_features(config)