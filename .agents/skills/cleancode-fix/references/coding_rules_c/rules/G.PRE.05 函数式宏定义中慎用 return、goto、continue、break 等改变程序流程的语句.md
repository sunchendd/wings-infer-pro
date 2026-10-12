# G.PRE.05 函数式宏定义中慎用 return、goto、continue、break 等改变程序流程的语句

- **规则ID**：2b85a5b1-33d6-410c-a141-047dc9905aed
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

函数式宏定义中慎用return、goto、continue、break等改变程序流程的语句。

**【正确示例】**

```
##### 场景1：函数式宏定义中使用return
- 修复示例：

```cpp
// 符合
void Func(int parm)
{
    if (parm == 1) {
        return;
    }
}
```

```
**【错误示例】**

```
##### 场景1：函数式宏定义中使用return
- 错误示例：

```cpp
// 不符合
#define XX(parm)     \
    if (parm == 1) { \
        return;      \
    }
```

```
**【修复建议】**

函数式宏定义中不要用return、goto、continue、break等改变程序流程的语句。
