# G.EXP.26-CPP 整型表达式比较或赋值为一种更大类型之前必须用这种更大类型对它进行求值

- **规则ID**：d5a2df9a-0b45-4b8f-9c9e-8896472f36ec
- **更新时间**：2025-03-25 19:23:42

---

**【问题级别】**

严重

**【描述】**

由于整数在运算过程中可能出现有符号整数溢出、无符号整数回绕等问题，当运算结果赋值给比它更大的类型，或者与比它更大的类型进行比较时，可能会导致实际结果与预期结果不符。



如果将涉及某个操作的整数表达式与较大的整数进行比较或者赋值给较大的整数，则应该将这个整数表达式中的一个操作数显式转换为较大的整数类型。

**【正确示例】**

```
如下的一种解决方案，是显式转换变量 a 和 b 的类型为 uint64_t 类型。

uint32_t a = 0xffffffffU;
uint32_t b = 1;
uint64_t c = 2;
uint64_t x = static_cast<uint64_t>(a) + static_cast<uint64_t>(b) + c;
uint64_t y = (static_cast<uint64_t>(a) + static_cast<uint64_t>(b)) + c;
uint64_t z = static_cast<uint64_t>(a) + c + static_cast<uint64_t>(b);
uint64_t t = static_cast<uint64_t>(a) + (static_cast<uint64_t>(b) + c);
uint64_t m = static_cast<uint64_t>(a) + static_cast<uint64_t>(b) * c;
最佳做法是修改变量 a 和 b 的类型为 uint64_t 类型，保持表达式中的操作数类型一致（如果表达式的数值不可信，应先校验其范围防止无符号整数回绕）。

uint64_t a = 0xffffffffU;
uint64_t b = 1;
uint64_t c = 2;
uint64_t x = a + b + c;
uint64_t y = a + c + b;
uint64_t z = a + (b + c);
uint64_t t = a + b * c;

```
**【错误示例】**

```
在以二进制补码表示整数的系统中：

表达式 a + b + c 等同于表达式 (a + b) + c，计算组合表达式 (a + b) 时先发生整数回绕，其结果为0，再与c相加后得到 x 的值为2
表达式 static_cast<uint64_t>(a + b) + c ，计算组合表达式(a + b)时先发生整数回绕，其结果为0，然后再转换 uint64_t 类型并与 c 相加后得到 y 的值为2
表达式 a + c + b 等同于表达式 (a + c) + b，与前面表达式不同点在于，计算a + c时发生了隐式类型转换，将 a 隐式提升到了 uint64_t 类型后在进行计算，因此最后 z 的值是正确的，但是该代码依赖表达式计算顺序，不利于维护和阅读，应禁止使用该技巧。类似的，t 和 m 的值虽然正确，但是依赖表达式优先级，应禁止使用该技巧
uint32_t a = 0xffffffffU;
uint32_t b = 1;
uint64_t c = 2;
uint64_t x = a + b + c;                        // 结果非预期, x的值为2
uint64_t y = static_cast<uint64_t>(a + b) + c; // 结果非预期, y的值为2
uint64_t z = a + c + b;                        // 结果正确，但是依赖表达式顺序，禁止使用该技巧
uint64_t t = a + (b + c);                      // 结果正确，但是依赖表达式优先级，禁止使用该技巧
uint64_t m = a + b * c;                        // 结果正确，但是依赖表达式优先级，禁止使用该技巧

```
**【修复建议】**

如果将涉及某个操作的整数表达式与较大的整数进行比较或者赋值给较大的整数，则应该将这个整数表达式中的一个操作数显式转换为较大的整数类型。
