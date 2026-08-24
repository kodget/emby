import os

def w(path, content):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    print(f'Created {path}')

Q = chr(34)

# MCQ Question Card
mcq = [
  Q+'use client'+Q+';',
  '',
  'import { motion } from '+Q+'framer-motion'+Q+';',
  'import { Flag, CheckCircle } from '+Q+'lucide-react'+Q+';',
  'import { Badge } from '+Q+'@/components/ui/badge'+Q+';',
  'import { Button } from '+Q+'@/components/ui/button'+Q+';',
  'import { cn } from '+Q+'@/lib/utils'+Q+';',
  'import type { QuizQuestion } from '+Q+'@/store/quiz-attempt-slice'+Q+';',
  '',
  'interface MCQQuestionCardProps {',
  '  question: QuizQuestion;',
  '  questionNumber: number;',
  '  totalQuestions: number;',
  '  selectedOption?: string;',
  '  isFlagged: boolean;',
  '  onSelect: (option: string) => void;',
  '  onFlag: () => void;',
  '}',
  '',
  'const OPTIONS = ['+Q+'A'+Q+', '+Q+'B'+Q+', '+Q+'C'+Q+', '+Q+'D'+Q+'] as const;',
  '',
  'function getOptionText(q: QuizQuestion, opt: string) {',
  '  const map: Record<string, string | undefined> = { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d };',
  '  return map[opt];',
  '}',
  '',
  'export function MCQQuestionCard({ question, questionNumber, totalQuestions, selectedOption, isFlagged, onSelect, onFlag }: MCQQuestionCardProps) {',
  '  return (',
  '    <motion.div key={question.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className='+Q+'space-y-6'+Q+'>',
  '      <div className='+Q+'flex items-start justify-between gap-4'+Q+'>',
  '        <div className='+Q+'flex-1'+Q+'>',
  '          <div className='+Q+'flex flex-wrap items-center gap-2 mb-3'+Q+'>',
  '            <Badge variant='+Q+'outline'+Q+' className='+Q+'text-xs'+Q+'>Question {questionNumber} of {totalQuestions}</Badge>',
  '            <Badge variant='+Q+'secondary'+Q+' className='+Q+'text-xs capitalize'+Q+'>{question.difficulty}</Badge>',
  '            {question.topic_name && <Badge variant='+Q+'outline'+Q+' className='+Q+'text-xs text-primary border-primary/30'+Q+'>{question.topic_name}</Badge>}',
  '          </div>',
  '          <p className='+Q+'text-lg font-medium leading-relaxed'+Q+'>{question.question_text}</p>',
  '        </div>',
  '        <Button variant='+Q+'ghost'+Q+' size='+Q+'icon'+Q+' onClick={onFlag}',
  '          className={cn('+Q+'flex-shrink-0 rounded-full transition-colors'+Q+', isFlagged ? '+Q+'text-amber-500 bg-amber-50 hover:bg-amber-100'+Q+' : '+Q+'text-muted-foreground'+Q+')}>',
  '          <Flag className='+Q+'w-4 h-4'+Q+' />',
  '        </Button>',
  '      </div>',
  '      <div className='+Q+'grid gap-3'+Q+'>',
  '        {OPTIONS.map((opt) => {',
  '          const text = getOptionText(question, opt);',
  '          if (!text) return null;',
  '          const selected = selectedOption === opt;',
  '          return (',
  '            <motion.button key={opt} whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }} onClick={() => onSelect(opt)}',
  '              className={cn('+Q+'w-full text-left p-4 rounded-xl border-2 transition-all duration-200 flex items-start gap-3'+Q+',',
  '                selected ? '+Q+'border-primary bg-primary/5 shadow-sm'+Q+' : '+Q+'border-border hover:border-primary/40 hover:bg-accent/40'+Q+')}>',
  '              <div className={cn('+Q+'w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold transition-all'+Q+',',
  '                selected ? '+Q+'bg-primary text-primary-foreground'+Q+' : '+Q+'bg-muted text-muted-foreground'+Q+')}>',
  '                {selected ? <CheckCircle className='+Q+'w-4 h-4'+Q+' /> : opt}',
  '              </div>',
  '              <span className='+Q+'pt-0.5 leading-relaxed text-sm'+Q+'>{text}</span>',
  '            </motion.button>',
  '          );',
  '        })}',
  '      </div>',
  '    </motion.div>',
  '  );',
  '}',
]
w('components/quiz/mcq-question-card.tsx', chr(10).join(mcq))

