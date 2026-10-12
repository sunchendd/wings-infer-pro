# G.FUN.02-CPP 函数的所有声明必须与定义具有一致的参数名

- **规则ID**：7d539eb8-0b76-4375-b1cf-f8bfd8ebb6d7
- **更新时间**：2025-03-25 19:21:59

---

**【问题级别】**

严重

**【描述】**

参数名可以提供关于函数接口的有用信息，声明和定义之间的不一致可能导致编程错误。



函数声明中的参数应该包含参数名，并且函数定义与其声明中的参数类型以及参数名需要保持一致。但是函数指针中的参数名与其指向函数的参数名可以不一致。

**【正确示例】**

```
// Fun.h  
void Fun1(int num);
void Fun2(int num, int count);
// Fun.cpp
void Fun1(int num)
{
    ...
}

void Fun2(int num, int count)
{
    ...
}

```
**【错误示例】**

```
// Fun.h  
void Fun1(int);  // 不符合：缺少参数名，应修改为void Fun1(int num)  

// 不符合：参数名不匹配，应修改为 void Fun2(int num, int count)  
void Fun2(int count, int num);
// Fun.cpp
void Fun1(int num)
{
    ...
}

void Fun2(int num, int count)
{
    ...
}

```
**【修复建议】**

声明和定义保持一致
