# G.PRE.01 使用函数代替函数式宏

- **规则ID**：ac51d54c-6006-4fe1-9c5f-cda6653533e4
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

定义函数式宏前，应考虑能否用函数替代。对于可替代场景，建议用函数替代宏。

**【正确示例】**

```
##### 场景1：函数式宏缺乏类型检查
- 修复示例：

```cpp
int Max(int a, int b)  // 符合，输出结果是：“FUNC : max of a(1) and b(-1) is 1”
{
    return (a < b) ? b : a;
}

void TestMacro(void)
{
    unsigned int a = 1;
    int b = -1;
    (void)printf("FUNC : max of a(%u) and b(%d) is %d
", a, b, Max(a, b));
}
```

```
**【错误示例】**

```
##### 场景1：函数式宏缺乏类型检查
- 错误示例：

```cpp
#define MAX(a, b) (((a) < (b)) ? (b) : (a)) // 不符合，由于宏缺乏类型检查，MAX中的a和b的比较提升为无符号数的比较，结果是a < b。输出结果是：“MACRO: max of a(1) and b(-1) is -1”

void TestMacro(void)
{
    unsigned int a = 1;
    int b = -1;
    (void)printf("MACRO: max of a(%u) and b(%d) is %d
", a, b, MAX(a, b));
}
```

```
**【修复建议】**

用函数代替函数式宏。
