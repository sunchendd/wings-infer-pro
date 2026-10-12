# G.INT.05 只能对无符号整数进行位运算

- **规则ID**：821ef92f-aedd-498f-b0e4-09ddf1b516bd
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

有符号整数的位操作的结果在C语言规范中是未定义的，最终结果由编译器实现确定。



为避免代码运行结果依赖于编译器实现，规范要求有符号数应避免进行位运算。

**【正确示例】**

```
##### 场景1：位运算(求反`~`)的操作数为有符号类型
- 修复示例1：
```c
uint32_t BitwiseOperationUnaryNotSignedGood02()
{
    uint32_t target = 0;
    /* Good: 对无符号整数进行位运算：~(求反) */
    return ~target;
}
```
##### 场景2：位运算(与`&`)的操作数为有符号类型
- 修复示例1：
```c
uint32_t BitwiseOperationBinaryAndSignedGood01(uint32_t input)
{
    /* Good: 无符号整数进行位运算 */
    return input & 1;
}
```
- 修复示例2：
```c
uint32_t BitwiseOperationBinaryAndSignedGood02(int input)
{
    /* Good: 无符号整数进行位运算 */
    return (uint32_t )input & 1;
}
```
##### 场景3：unsigned char/unsigned short类型取反后右移告警
- 修复示例1：
```c
uint32_t BitwiseOperationUnaryNotSignedGood01()
{
    uint32_t target = 0;
    /* Good */
    return target >> 1;
}
```


```
**【错误示例】**

```
##### 场景1：位运算(求反`~`)的操作数为有符号类型
- 错误示例1：

```c
int BitwiseOperationUnaryNotSignedBad01()
{
    int target = 0;
    /* 不符合: 对有符号整数进行位运算：~(求反) */
    target = ~target;
    return target;
}
```
##### 场景2：位运算(与`&`)的操作数为有符号类型
- 错误示例：
```c
int BitwiseOperationBinaryAndSignedBad01(int input)
{
    /* 不符合: 对有符号整数进行位运算：&(与) */
    return input & 1;
}
```
##### 场景3：unsigned char/unsigned short类型取反后右移告警
- 错误示例1：
```c
unsigned char BitwiseOperationUnaryNotSignedBad01()
{
    unsigned char target = 0;
    /* 不符合: 对unsigned char类型整数取反后右移 */
    return target >> 1;
}
```


```
**【修复建议】**

位操作符（`～`、`>>`、`<<`、`&`、`^`、`|`)应该只用于无符号整型操作数。

注意：即使有符号变量是正数也是不符合规范的，需要整改。



建议方法1（优选）：如果变量从语义上、逻辑上、使用上确保是正数，变量类型应改为无符号类型。

建议方法2：强转为无符号类型后进行位运算。
