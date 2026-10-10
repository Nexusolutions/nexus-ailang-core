# AILang EBNF (Nivel D, resumen normativo)

```
program        ::= { statement }
statement      ::= let_stmt | const_stmt | fn_stmt | async_fn | class_stmt
                 | enum_stmt | if_stmt | while_stmt | for_stmt | match_stmt
                 | return_stmt | break | continue | import_stmt
                 | try_stmt | throw_stmt | assign_or_expr

let_stmt       ::= "let" IDENT [ ":" IDENT ] "=" expression
const_stmt     ::= "const" IDENT [ ":" IDENT ] "=" expression
fn_stmt        ::= "fn" IDENT "(" [ params ] ")" block
async_fn       ::= "async" fn_stmt
enum_stmt      ::= "enum" IDENT "{" IDENT { "," IDENT } "}"
class_stmt     ::= "class" IDENT [ "extends" IDENT ] "{" { fn_stmt } "}"
match_stmt     ::= "match" expression "{" { "case" pattern block } "}"
pattern        ::= literal | IDENT | "_"

expression     ::= logic
logic          ::= comparison { ("and"|"or") comparison }
comparison     ::= term { ("=="|"!="|"<"|"<="|">"|">=") term }
term           ::= factor { ("+"|"-") factor }
factor          ::= unary { ("*"|"/"|"%") unary }
unary          ::= [ "not"|"-"|"await" ] unary | call
call           ::= primary { "(" args ")" | "." IDENT | "[" expression "]" }
primary        ::= NUMBER | STRING | IDENT | "true"|"false"|"null"
                 | "(" expression ")" | list | dict | lambda
block          ::= "{" { statement } "}"
```
