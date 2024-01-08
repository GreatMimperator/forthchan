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
<cycle-term> ::= <term> | "leave"
<for-cycle> ::= do [i] <cycle-term> loop
<do-while-cycle> ::= begin <cycle-term> until
<word-def> ::= ":"<word><term except <word>>";"
<printable-chars> ::= 
<print-char-sequence> ::= ."<acsii symbol except '"'>"
```