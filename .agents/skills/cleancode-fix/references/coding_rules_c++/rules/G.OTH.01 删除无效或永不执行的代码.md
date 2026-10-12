# G.OTH.01 删除无效或永不执行的代码

- **规则ID**：5f099338-3048-4001-b32c-ee3dc4042ecf
- **更新时间**：2025-03-25 19:23:07

---

**【问题级别】**

严重

**【描述】**

无效或永不执行的代码（即无效代码或无法访问的代码）通常是编程错误的结果，并且可能导致意外行为。通常在编译时，编译器会对此类代码进行优化。但是，为了提高可读性并确保解决逻辑错误，应该主动对其进行识别，理解和消除。



虽然大多数现代编译器在许多情况下可以对无效或从不执行的代码告警，但程序员还是应该主动识别无效的语句或表达式，并将其从代码中删除。

**【正确示例】**

```
删除无效代码取决于程序员的意图，下面代码是一种改进方案。
int Func(int condVal)
{
    if (condVal == 1) {
        char *s = (char *)malloc(ALLOC_SIZE);
        if (s == NULL) {
           ... // 错误处理
        }
        ... // 处理 s
        free(s);
        return 0;
    }
    ...
    return 0;
}

该代码可能是程序员错误的使用相等操作符(==)而不是赋值操作符(=)的情况。
int a = ...;
int b = ...;
...
a = b;

更正此示例取决于程序员的意图。例如，如果解引用p是错误的，则p不应解引用。
int *p = NULL;
...
p++;

if (param == 1) {
    DoSomething1();
} else if (param == 2) {
    DoSomething2();
} else if (param == 3) {
    DoSomething3();
} else {
    ...
}

```
**【错误示例】**

```
下面代码中，最后的 if 条件语句永远无法成立，应该删除或重新优化代码。
int Func(int condVal)
{
    char *s = NULL;
    if (condVal == 1) {
        s = (char *)malloc(ALLOC_SIZE);
        if (s == NULL) {
           ... // 错误处理
        }
        ... // 处理 s
        return 0;
    }
    ...
    if (s != NULL) {
        ... // 此处代码不可达
    }
    return 0;
}

下面代码进行了a与b的比较，没有任何效果。
int a = ...;
int b = ...;
...
a == b; // 不符合： 这一行代码没有任何作用

如下代码示例中，对指针进行解引用后，指针值增加了，但解引用没有任何作用。
int *p = NULL;
...
*p++;

从上到下评估一串if/else if语句。最多只执行该链的一个分支：第一个分支的条件求值为true。因此，在if/else if语句序列中复制条件会自动导致无效代码。
if (param == 1) {
    DoSomething1();
} else if (param == 2) {
    DoSomething2();
} else if (param == 1) {  // 条件重复，永远不成立，预期是3？
    DoSomething3();
} else {
    ...
}

```
**【修复建议】**

删除不可执行代码
