# G.INT.01 确保有符号整数运算不溢出

- **规则ID**：ea869131-f555-4a77-b45e-5ce7411873ff
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

算术运算导致的溢出和回绕可能导致缓冲区溢出、执行任意代码等问题。

因此，对于算术运算（包括加、减、乘、递增和递减）的操作数要进行合理校验，防止出现溢出和回绕。

**【正确示例】**

```
##### 场景1：加法算术运算导致整数溢出。
- 修复示例：对于算术运算的操作数，在使用前做严格的范围校验，用以保证算术运算时不会出现溢出、回绕。

```c
const int DATA_MAX = 100;
const int DATA_MIN = -100;
void AddGood(int data, int offset)
{
    // 校验data是否在合法范围内
    if (data < DATA_MIN || data > DATA_MAX) {
        return;
    }
    // 符合：校验后的数据加法不会溢出
    int newData = data + offset;
    printf("%d
", newData);
}

void Foo()
{
    AddGood(INT_MAX  - 9, 10);
}
```
##### 场景2：减法算术运算导致整数溢出。
- 修复示例：对于算术运算的操作数，在使用前做严格的范围校验，用以保证算术运算时不会出现溢出、回绕。

```c
const int DATA_MAX = 100;
void SubGood(unsigned char data)
{
    // 校验data是否在合法范围内
    if (data < 1 || data > DATA_MAX) {
        return;
    }
    // 符合：校验后的数据减法不会溢出
    unsigned char newData = data - 1;
    printf("%u
", newData);
}

void Foo()
{
    AddGood(INT_MAX);
}
```
##### 场景3：乘法算术运算导致整数回绕。
- 修复示例：对于算术运算的操作数，在使用前做严格的范围校验，用以保证算术运算时不会出现溢出、回绕。

```c
void MulGood(unsigned int data)
{
    // 校验data是否在合法范围内
    if (data == 0 || data > (UINT_MAX / 2)) {
        return;
    }
    // 符合：校验后的数据乘法不会回绕
    unsigned int newData = data * 2;
    printf("%u
", newData);
}

void Foo()
{
    MulGood(UINT_MAX);
}
```
##### 场景4：整数之间强制转换导致数据截断。
- 修复示例：对于强制转换的变量，在转换前做范围校验，用以保证转换时不会出现截断。

```c
unsigned char CastGood()
{
    unsigned char a = 100;
    unsigned char b = 200;
    // 校验a和b是否在合法范围内
    if (a > UCHAR_MAX - b) {
        return 0;
    }
    // 符合：校验后的数据不会数据截断
    return a + b;
}
```


```
**【错误示例】**

```
##### 场景1：加法算术运算导致整数溢出。
- 错误示例：

```c
void AddBad(int data, int offset)
{
    // 不符合：传入data的值是INT_MAX - 9，offset是10时， data + offset的值超出int类型最大值，导致加法溢出
    int newData = data + offset;
    printf("%d
", newData);
}

void Foo()
{
    AddBad(INT_MAX - 9, 10); // 输出结果是：-2147483648
}
```
##### 场景2：减法算术运算导致整数溢出。
- 错误示例：

```c
const int DATA_MAX = 100;
void SubBad(unsigned char data)
{
    if (data > DATA_MAX) {
        return;
    }
    // 不符合：data的取值范围是[0, DATA_MAX)，如果data为0，0值减1赋值给无符号类型，翻转成超大正数
    unsigned char newData = data - 1;
    printf("%u
", newData);
}

void Foo()
{
    SubBad(0); // 输出结果是：255
}
```
##### 场景3：乘法算术运算导致整数回绕。
- 错误示例：

```c
void MulBad(unsigned int data)
{
    // 不符合：传入data的值为UINT_MAX时，data * 2的值超出unsigned int类型最大值，导致回绕
    unsigned int newData = data * 2;
    printf("%u
", newData);
}

void Foo()
{
    MulBad(UINT_MAX - 1); // 输出结果是：4294967292
}
```
##### 场景4：整数之间强制转换导致数据截断。
- 错误示例：

```c
unsigned char CastBad01()
{
    unsigned char a = 100;
    unsigned char b = 200;
    // 不符合：a和b变量先整数提升到int类型，相加后是300，大于unsigned char类型最大值，强制转换后导致数据截断
    return a + b;
}
unsigned char CastBad02()
{
    unsigned char a = 100;
    unsigned char b = 200;
    // 不符合：显式强转截断，此场景通过report_explicit_cast选项控制
    return (unsigned char)(a + b);
}
```


```
**【修复建议】**

1. 对于算术运算（包括加、减、乘、递增和递减）的操作数，在使用前做严格的范围校验，建议对于有符号操作数做上下限校验，对无符号操作数至少做上限校验，用以保证算术运算时不会出现溢出、回绕。

2. 对于强制转换的变量，在转换前做范围校验，建议对于有符号操作数做上下限校验，对无符号操作数至少做上限校验，用以保证转换时不会出现截断。
