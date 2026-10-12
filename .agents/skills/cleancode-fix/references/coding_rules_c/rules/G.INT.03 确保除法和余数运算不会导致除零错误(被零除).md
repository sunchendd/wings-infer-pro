# G.INT.03 确保除法和余数运算不会导致除零错误(被零除)

- **规则ID**：cfac4beb-2089-4c47-94bd-6df4d534cd27
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

在整型变量未作非零校验的情况下，变量作为除数进行运算，变量值可能为0，从而会出现程序产生未定义的行为的问题。因此，如果涉及到除法或者取余运算，必须确保除数变量值不为0。

当前，规则仅检查除数明确为0的场景。针对除数无法计算，有可能为0的场景都不检查。

**【正确示例】**

```
##### 场景1：if条件不成立时，出现除零错误。
- 修复示例1：校验作为除数的值，确保不为0。

```c
int32_t Cond01(int32_t var)
{
    if (var > 5) {
        return 1;
    } else {
        return 0;
    }
}

int32_t GoodCase01(int32_t var)
{
    int32_t x = 0;
    if (Cond01(var)) {
        x = 1;
    }
    if (x == 0) { // 符合：增加校验
        return -1;
    }
    // 符合
    return 1 / x;
}
```
##### 场景2：使用可能为0的函数返回值做除数。
- 修复示例1：对返回值进行非0校验

```c
int32_t Foo02(int32_t var)
{
    if (var < 0) {
        return 0;
    }
    return var;
}

void GoodCase02(int32_t var)
{
    int32_t x = Foo02(var);
    if (x == 0) { // 符合：增加校验
        return;
    }
    // 符合
    int32_t z = 1 / x;
}
```

```
**【错误示例】**

```
##### 场景1：if条件不成立时，出现除零错误。
- 错误示例：

```c
int32_t Cond01(int32_t var)
{
    if (var > 5) {
        return 1;
    } else {
        return 0;
    }
}


int32_t BadCase01(int32_t var)
{
    int32_t x = 0;
    if (Cond01(var)) { // if 条件不成立时，出现除零错误
        x = 1;
    }
    // 不符合: 除零错误
    return 1 / x;
}
```
##### 场景2：使用可能为0的函数返回值做除数。
- 错误示例：

```c
int32_t Foo02(int32_t var)
{
    if (var < 0) {
        return 0;
    }
    return var;
}

void BadCase02(int32_t var)
{
    // 不符合: 除零错误
    int32_t z = 1 / Foo02(var);
}
```

```
**【修复建议】**

校验作为除数的值，确保不为0。在除法之前，进行判断。
