# G.TYP.04 避免隐式有损算术转换

- **规则ID**：213be66c-2c40-43ba-a810-49ff4709d4c9
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

做数据有损的算术转换会破坏数据信息，特别是隐式有损的算术转换，其错误不易察觉，所以应尽量避免隐式有损算术转换。

**【正确示例】**

```
##### 场景1：做隐式有损算术转换（double转int）
- 修复示例1：如果不需要做有损算术转换，修改为相同类型操作。

```c
void NarrowArithmeticGood01()
{
    double d = 8.2;
    // 符合：使用相同类型
    double i = d;
}
```
- 修复示例2：如果必须做有损算术转换，应当明确使用**显式类型转换操作**将数据转换到指定的类型。

```c
void NarrowArithmeticGood02()
{
    double d = 8.2;
    // 符合：显式double转int
    int i = (int)d;
}
```
##### 场景2：做隐式有损算术转换（float转char）
- 修复示例1：如果不需要做有损算术转换，修改为相同类型操作。

```c
void NarrowArithmeticGood01()
{
    float d = 8.2;
    // 符合：使用相同类型
    float f = d;
}
```
- 修复示例2：如果必须做有损算术转换，应当明确使用**显式类型转换操作**将数据转换到指定的类型。

```c
void NarrowArithmeticGood02()
{
    float d = 8.2;
    // 符合：显式float转char
    char c = (char)d;
}
```


```
**【错误示例】**

```
##### 场景1：做隐式有损算术转换（double转int）
- 错误示例：

```c
void NarrowArithmeticBad01()
{
    double d = 8.2;
    // 不符合：数据有损的窄化，double转int
    int i = d;
}
```
##### 场景2：做隐式有损算术转换（float转char）
- 错误示例：

```c
void NarrowArithmeticBad02()
{
    float d;
    ...
    d = 8.2;
    // 不符合：数据有损的窄化，float转char
    char c = d;
}
```


```
**【修复建议】**

1. 如果不需要做有损算术转换，修改为相同类型操作。

2. 如果必须做有损算术转换，应当明确使用**显式类型转换操作**将数据转换到指定的类型。
