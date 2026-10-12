# G.INT.04 整型表达式比较或赋值为一种更大类型之前必须用这种更大类型对它进行求值

- **规则ID**：ad1c7787-5858-453e-9300-125a833bac50
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

致命

**【描述】**

由于整数在运算过程中可能出现有符号整数溢出、无符号整数回绕等问题，当运算结果赋值给比它更大的类型，或者与比它更大的类型进行比较时，可能会导致实际结果与预期结果不符。

如果将涉及某个操作的整数表达式与较大的整数进行比较或者赋值给较大的整数，则应该将这个整数表达式中的一个操作数显式转换为较大的整数类型。

**【正确示例】**

```
##### 场景1：算术运算（加法）表达式的值可能在结果被赋值给较大的数据类型之前溢出
```cpp
int OverflowBeforeIntegerWidenCombinationBadCase01()
{
    uint32_t a = 0xffffffffU;
    uint32_t b = 1;
    uint64_t c = 2;
    /* 表达式 a + b + c 等同于表达式 (a + b) + c ，计算组合表达式 (a + b) 时先发生整数回绕 */
    uint64_t x = (uint64_t)a + b + c;
    return 0;
}
```

##### 场景2：算术运算（乘法）表达式的值可能在结果被赋值给较大的数据类型之前溢出
```cpp
int OverflowBeforeIntegerWidenBadCase07()
{
    uint32_t a = 0x10000000;
    /* uint32_t类型乘法赋值和uint64_t类型 */
    uint64_t b = (uint64_t)a * 0xab;
    std::cout << b << std::endl;
    return 0;
}
```

##### 场景3：算术运算（乘法）表达式的值可能在结果与较大的数据类型比较之前溢出
```cpp
// @scene 两个 uint32_t 类型变量做乘法之后与 uint64_t 类型变量做 < 比较
void OverflowBeforeIntegerWidenBadCase03()
{
    uint32_t x = 2147483648;
    uint32_t y = 2;
    uint64_t z = 0;
    /* x * y 超过了目标平台的 unsigned 类型允许的最大值（2^32 − 1，即 4,294,967,295） */
    if (((uint64_t)x * y) < z) {
        x = 0;
        y = 0;
    }
}
```

```
**【错误示例】**

```
##### 场景1：算术运算（加法）表达式的值可能在结果被赋值给较大的数据类型之前溢出
错误示例：
```cpp
#include <cstdint>
#include <iostream>
int OverflowBeforeIntegerWidenCombinationBadCase01()
{
    uint32_t a = 0xffffffffU;
    uint32_t b = 1;
    uint64_t c = 2;
    /* 不符合: 表达式 a + b + c 等同于表达式 (a + b) + c ，计算组合表达式 (a + b) 时先发生整数回绕 */
    uint64_t x = a + b + c;
    return 0;
}
```
##### 场景2：算术运算（乘法）表达式的值可能在结果被赋值给较大的数据类型之前溢出
错误示例：
```cpp
#include <cstdint>
#include <iostream>
int OverflowBeforeIntegerWidenBadCase07()
{
    uint32_t a = 0x10000000;
    /* 不符合: uint32_t类型乘法赋值和uint64_t类型 */
    uint64_t b = a * 0xab;
    std::cout << b << std::endl;
    return 0;
}
```
##### 场景3：算术运算（乘法）表达式的值可能在结果与较大的数据类型比较之前溢出
错误示例：
```cpp
#include <cstdint>
#include <iostream>
// @scene 两个 uint32_t 类型变量做乘法之后与 uint64_t 类型变量做 < 比较
void OverflowBeforeIntegerWidenBadCase03()
{
    uint32_t x = 2147483648;
    uint32_t y = 2;
    uint64_t z = 0;
    /* 不符合: x * y 超过了目标平台的 unsigned 类型允许的最大值（2^32  1，即 4,294,967,295） */
    if ((x * y) < z) {
        x = 0;
        y = 0;
    }
}
```

```
**【修复建议】**

如果将涉及某个操作的整数表达式与较大的整数进行比较或者赋值给较大的整数：

- 最佳做法是修改变量类型，保持表达式中的操作数类型一致（如果表达式的数值不可信，应先校验其范围防止无符号整数回绕）。

- 可以将这个整数表达式中的一个操作数显式转换为较大的整数类型。
