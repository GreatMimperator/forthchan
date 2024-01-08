# Forthchan
Зенин Мирон Александрович, Группа P33101  
Вариант: `forth | stack | neum | hw | tick | struct | trap | port | cstr | prob5 | spi`  
Без усложнения  
# Язык программирования
```ebnf
<program> ::= <term>

<term> ::= <term> <term> | 
   <number> | 
   <word> | 
   <sign-word> |
   <comment> | 
   <for-cycle> | 
   <do-while-cycle> |
   <if-statement> |
   <word-def> |
   <print-char-sequence>
<sign-word> ::= + | - | / | *
<digit> ::= 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9
<digit-sequence> ::= <digit>[<digit>]
<starting-digit> ::= <digit> \ 0
<number> ::= [-]<digit> | [-]<starting-digit><digit-sequence>
<latyn> ::= a | b | c | ... | z | A | ... | Z
<word-possible-symbol> ::= <latyn> | -
<word> ::= <latyn> [<word-possible-symbol> <word>]
<comment> ::= "\" <any-symbol-sequence>
<contructive-term> ::= <term> \ <word-def>
<cycle-term> ::= <contructive-term> | "leave"
<for-cycle> ::= do [i] <cycle-term> loop
<do-while-cycle> ::= begin <cycle-term> until
<if-statement> ::= if <contructive-term> [else <contructive-term>] then
<word-def> ::= ":"<word><contructive-term>";"
<print-char-sequence> ::= ."<acsii symbol except '"'>"
```
Определения слов (<word-def>) имеют глобальную область видимости и не выполняются непосредственно,
остальные члены (<term>) (в том числе и внутри вызываемых слов) исполняются последовательно

В языке определено некоторое множество слов (`<word>`), которые реализованы как инструкции.
Так как память стековая (для стека память выделяется статически при запуске модели), 
операции выполняются со стеком.  
`<number>` - добавляет на верхушку стека это число  
Описание `<sign-word>`:  
- `+` - вынуть два числа из верхушки стека и запушить их сумму
- `-`, `/`, `*` - то же, но (из дальнего верхушку стека) разность, частное и произведение
`<comment>` можно добавить в конце строки, все что после символа `\` игнорируется.  
Что касается остальных термов - все это возможно помещать без переноса строчки,
главное лишь соблюсти расстояние в виде обязательного знака пробела.  
`<for-cycle>` - для его переменных выделен отдельный стек (для всех таких циклов сразу), 
`do [i]` поглощает два числа с верхушки стека: 
до какого (исключительно) двигаться и с какого начать с шагом 1. 
Если указано `i`, то в общий стек помещается переменная цикла.
Исполнение термов идет до соответствующего `loop`, а там счетчик увеличивается и выполняется перемещение к первому из термов цикла  
`leave` во обоих видах циклов вызывает переход к исполнению первого после цикла терма  
`<do-while-cycle>` - в нем на "until" вытаскивается число из стека, и если оно 0 (true), 
то цикл продолжается с первого из термов цикла (т.е. после `begin`)  
`<if-statement>` - поглощает верхушку стека и если она 0 (true), то выполняются термы после if, а термы else игнорируются
в случае неравенства 0 (false) выполняются только термы после else, термы же после if игнорируются  
`<word-def>` - слово определяется глобально, доступно для применения отовсюду. 
В месте использования слова (`<word>`) исполняются все принадлежащие определению термы.
Исключение - встроенные слова  
`<print-char-sequence>` - печатает последовательность символов ascii, указанную между двойными кавычками в консоль  

