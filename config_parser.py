import re
from typing import Dict, List, Tuple
from pydantic import BaseModel, Field


class AnswerOption(BaseModel):
    """Вариант ответа с весом."""
    text: str
    weight: float = Field(ge=0.0, le=1.0)


class Question(BaseModel):
    """Вопрос с вариантами ответов."""
    question_text: str
    question_type: str  # "radio" или "checkbox"
    answers: List[AnswerOption]


class SurveyConfig(BaseModel):
    """Конфигурация всего опроса."""
    questions: List[Question]


def parse_survey_config(md_content: str) -> SurveyConfig:
    """
    Парсит .md файл с конфигурацией опроса от AI агента.
    
    Ожидаемый формат:
    ### Вопрос N: [Текст вопроса]
    Тип: radio / checkbox
    
    Ответы:
    - Вариант ответа 1: 0.XX
    - Вариант ответа 2: 0.XX
    """
    questions = []
    
    # Разделяем на блоки вопросов
    question_blocks = re.split(r'###\s+Вопрос\s+\d+:', md_content)
    
    for block in question_blocks[1:]:  # Пропускаем первый пустой блок
        lines = block.strip().split('\n')
        if not lines:
            continue
        
        # Первая строка - текст вопроса
        question_text = lines[0].strip()
        
        question_type = "radio"
        answers = []
        
        i = 1
        while i < len(lines):
            line = lines[i].strip()
            
            # Тип вопроса
            if line.startswith('Тип:') or line.startswith('Type:'):
                q_type = line.split(':', 1)[1].strip().lower()
                if 'checkbox' in q_type:
                    question_type = "checkbox"
                else:
                    question_type = "radio"
            
            # Ответы
            elif line.startswith('Ответы:') or line.startswith('Answers:'):
                # Читаем все ответы
                i += 1
                while i < len(lines):
                    answer_line = lines[i].strip()
                    if not answer_line or answer_line.startswith('#'):
                        break
                    
                    # Формат: "- Вариант: 0.XX" или "Вариант: 0.XX"
                    if ':' in answer_line:
                        # Убираем "- " в начале
                        answer_line = answer_line.lstrip('- ').strip()
                        
                        # Разделяем на текст и вес
                        parts = answer_line.rsplit(':', 1)
                        if len(parts) == 2:
                            answer_text = parts[0].strip()
                            try:
                                weight = float(parts[1].strip())
                                answers.append(AnswerOption(text=answer_text, weight=weight))
                            except ValueError:
                                pass
                    
                    i += 1
                continue
            
            i += 1
        
        # Добавляем вопрос если есть текст и ответы
        if question_text and answers:
            questions.append(Question(
                question_text=question_text,
                question_type=question_type,
                answers=answers
            ))
    
    return SurveyConfig(questions=questions)


def load_survey_config(filepath: str) -> SurveyConfig:
    """Загружает конфигурацию опроса из файла."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return parse_survey_config(content)


