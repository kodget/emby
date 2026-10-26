# Services package

def __getattr__(name):
    # Rendering and text utilities also run in a small process without Django.
    # Importing this package must not initialize models or AI provider clients.
    from importlib import import_module
    if name == 'SubscriptionLimiter':
        return getattr(import_module('.quiz_permissions', __name__), name)
    if name in {'AIQuestionGenerator', 'question_generator', 'Gemini429Exception'}:
        return getattr(import_module('.ai_question_generator', __name__), name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

__all__ = [
    'AIQuestionGenerator',
    'question_generator',
    'Gemini429Exception',
    'SubscriptionLimiter',
]
