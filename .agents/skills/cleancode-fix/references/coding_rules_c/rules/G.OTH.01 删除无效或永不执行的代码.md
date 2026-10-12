# G.OTH.01 删除无效或永不执行的代码

- **规则ID**：ec1b6b1b-dbba-4888-aa7c-3c23220ce6ec
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

严重

**【描述】**

无效或永不执行的代码（如：死代码、恒真/恒假的表达式、空代码块、未被引用的代码等）通常是编程错误的结果，并且可能导致意外行为。

因此，应该主动识别并删除无效或永不执行的代码。

**【正确示例】**

```
##### 场景1：return之后的代码永不执行
- 修复示例：

```c
// 符合
int Foo() {
    return 0;
}
```
##### 场景2：goto之后的代码永不执行
- 修复示例：

```c
// 符合
int Foo(int x, int y)
{
    y++;
    if (x < 10) {
        y++;
        return y;
    }
    return x;
}
```
##### 场景3：无条件的break导致循环只执行一次
- 修复示例：

```c
// 符合
void Foo(const char *array, uint32_t len)
{
    for (uint32_t i = 0; i < len; i++) {
        if (array[i] > LEN_MAX) {
            array[i] = 0;
        }
    }
}
```

```
**【错误示例】**

```
##### 场景1：return之后的代码永不执行
- 错误示例：

```c
int Foo() {
    return 0;
    Bar(); // 不符合：该行及以下代码永不执行
    return x;
}
```
##### 场景2：goto之后的代码永不执行
- 错误示例：

```c
int Foo(int x, int y)
{
    y++;
    goto out;
    if (x < 10) { // 不符合：该行及以下代码永不执行
        y++;
        return y;
    }
out:
    return x;
}
```
##### 场景3：无条件的break导致循环只执行一次
- 错误示例：

```c
void Foo(const char *array, uint32_t len)
{
    for (uint32_t i = 0; i < len; i++) {
        if (array[i] > LEN_MAX) {
            array[i] = 0;
        }
        break; // 不符合：循环只执行一次就退出，循环递增i++没有执行过
    }
}
```

```
**【修复建议】**

删除无效或永不执行的代码。
