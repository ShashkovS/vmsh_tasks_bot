# -*- coding: utf-8 -*-
from enum import Enum, unique

from helpers.consts import VERDICT


@unique
class FEATURES(Enum):
    #### VERDICTS ####
    VERDICT_PLUS_MINUS = (VERDICT.SOLVED, VERDICT.WRONG_ANSWER)
    VERDICT_PLUS_MINUS_HALF = (VERDICT.SOLVED, VERDICT.VERDICT_PLUS_DIV_2, VERDICT.WRONG_ANSWER)
    VERDICT_PLUS_STEPS = (VERDICT.VERDICT_PLUS, VERDICT.VERDICT_PLUS_DOT, VERDICT.VERDICT_PLUS_MINUS, VERDICT.VERDICT_PLUS_DIV_2, VERDICT.VERDICT_MINUS_PLUS,
                          VERDICT.VERDICT_MINUS_DOT, VERDICT.VERDICT_MINUS)

    #### RESULTS ####
    RESULT_IMMEDIATELY = 'res_immed'
    RESULT_AFTER = 'res_after'

    #### SAVE SOLS ####
    SAVE_SOL_ON_DRIVE = 'save_on_drive'
    SAVE_SOL_IN_TG_ONLY = 'save_on_tg_only'



VERDICT_MODE = FEATURES.VERDICT_PLUS_STEPS
RESULT_MODE = FEATURES.RESULT_AFTER
SAVE_SOL_MODE = FEATURES.SAVE_SOL_ON_DRIVE
