# G.ARR.02 禁止通过对数组类型的函数参数变量进行sizeof来获取数组大小

- **规则ID**：90ef8462-afbf-4833-afa2-d937508b9912
- **更新时间**：2025-03-25 19:23:35

---

**【问题级别】**

一般

**【描述】**

使用sizeof操作符求其操作数的大小（以字节为单位），其操作数可以是一个表达式或者加上括号的类型名称，例如：sizeof(int)或sizeof(int *)。

参考C11标准6.5.3.4中的脚注103：



当将sizeof应用于具有数组或函数类型的参数时，sizeof操作符将得出调整后的（指针）类型的大小。



函数参数列表中声明为数组的参数会被调整为相应类型的指针。例如：void Func(int inArray[LEN])函数参数列表中的inArray虽然被声明为数组，但是实际上会被调整为指向int类型的指针，即调整为void Func(int *inArray)。

在这个函数内使用sizeof(inArray)等同于sizeof(int *)，得到的结果通常与预期不相符。例如：在IA-32架构上，sizeof(inArray) 的值是 4，并不是inArray数组的大小。

**【正确示例】**

```
如下代码示例中，修改函数定义，添加数组长度参数，并在调用处正确传入数组长度。

#define DATA_LEN 256
// 函数说明：入参len是入参inArray数组的长度
void ArrayInit(int inArray[], size_t len)
{
    for (size_t i = 0; i < len; i++) {
        ...
    }
}

void FunctionData(void)
{
    int data[DATA_LEN];

    ArrayInit(data, sizeof(data) / sizeof(data[0]));
    ...
}

如下代码示例中，使用入参len表示指定数组的长度：

#define ARRAY_MAX_LEN 256

// 函数说明：入参len是入参数组的长度
void ArrayInit(int inArray[], size_t len)
{
    for (size_t i = 0; i < len; i++) {
        ...
    }
}

int main(void)
{
    int masterArray[ARRAY_MAX_LEN];

    ArrayInit(masterArray, ARRAY_MAX_LEN);
    ...

    return 0;
}

```
**【错误示例】**

```
如下代码示例中，函数ArrayInit的功能是初始化数组元素。该函数有一个声明为int inArray[]的参数，被调用时传递了一个长度为256的int类型数组data。
ArrayInit函数实现中使用sizeof(inArray) / sizeof(inArray[0])方法来计算入参数组中元素的数量。
但由于inArray是函数参数，所以具有指针类型，结果，sizeof(inArray)等同于sizeof(int *)。
无论传递给ArrayInit函数的数组实际长度如何，表达式的sizeof(inArray) / sizeof(inArray[0])计算结果均为1，与预期不符。

#define DATA_LEN 256
void ArrayInit(int inArray[])
{
    // 不符合：这里使用sizeof(inArray)计算数组大小
    for (size_t i = 0; i < sizeof(inArray) / sizeof(inArray[0]); i++) {
        ...
    }
}

void FunctionData(void)
{
    int data[DATA_LEN];

    ...
    ArrayInit(data); // 调用ArrayInit函数初始化数组data数据
    ...
}



如下代码示例中，sizeof(inArray)不等于ARRAY_MAX_LEN * sizeof(int)，因为将sizeof操作符应用于声明为具有数组类型的参数时，即使参数声明指定了长度，也会被调整为指针，sizeof(inArray)等同于 sizeof(int *)：

#define ARRAY_MAX_LEN 256

void ArrayInit(int inArray[ARRAY_MAX_LEN])
{
    // 不符合：sizeof(inArray)，得到的长度是指针的大小，不是数组的长度，和预期不符。
    for (size_t i = 0; i < sizeof(inArray) / sizeof(inArray[0]); i++) {
        ...
    }
}

int main(void)
{
    int masterArray[ARRAY_MAX_LEN];

    ...
    ArrayInit(masterArray);

    return 0;
}

```
**【修复建议】**

禁止对指针变量进行sizeof操作。
