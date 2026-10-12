# G.EXP.08-CPP 确保对象在使用之前已被初始化

- **规则ID**：9722f301-7945-4c23-ad10-ac5ae6334748
- **更新时间**：2025-03-25 19:22:20

---

**【问题级别】**

严重

**【描述】**

本条款中的“初始化”指的是通过定义时显式初始化、默认构造初始化、赋值等方式使对象拥有期望的值。读取一个未初始化的值时，程序可能产生未定义行为，因此需要确保对象在使用之前已被初始化。

**【正确示例】**

```
void Bar(int data);
...
void Foo()
{
    int data = 0;               // 符合：显式初始化
    Bar(data);
    ...
}
void InitData(int& data);
...
void Foo()
{
    int data; 
    InitData(data);             // 符合：通过函数初始化
    ...
}
std::string data;               // 符合：默认构造函数初始化
...

```
**【错误示例】**

```
void Bar(int data);
...
void Foo()
{
    int data;
    Bar(data);                  // 不符合：未初始化就使用  
    ...
}
void Bar(int data);
...
void Foo(int condition)
{
    int data;
    if (condition > 0) {
        data = CUSTOMIZED_SIZE;
    }
    Bar(data);                  // 不符合：部分分支该值未初始化  
    ...
}

```
**【修复建议】**

变量使用前进行初始化
