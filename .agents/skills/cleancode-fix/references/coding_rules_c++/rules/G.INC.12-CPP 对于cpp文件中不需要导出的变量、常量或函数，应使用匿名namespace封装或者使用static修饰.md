# G.INC.12-CPP 对于cpp文件中不需要导出的变量、常量或函数，应使用匿名namespace封装或者使用static修饰

- **规则ID**：cd8e9371-85e3-4b75-a0c9-efc959e47762
- **更新时间**：2025-03-25 19:22:56

---

**【问题级别】**

一般

**【描述】**

对于cpp文件中不需要导出的变量、常量或函数，应使用匿名namespace封装或者用static修饰。



本条款推荐使用匿名namespace。主要原因如下：



static在C++中已经赋予了太多的含义，静态成员变量，静态成员函数，静态全局变量，静态函数局部变量，每一种都有特殊的处理

static只能保证变量，常量和函数的文件作用域，但是namespace还可以封装类型等

统一使用namespace来管理C++的作用域，而不需要同时使用static和namespace来管理

static修饰的函数不能用来实例化模板，而匿名namespace可以

没有extern修饰的const变量默认只有internal linkage属性，如果需要定义仅供cpp文件内使用的const变量，不必使用匿名namespace或者static修饰。但如果与其他不需要导出的符号成组出现，推荐使用匿名namespace统一管理。



另外，不要在 .h 中使用匿名namespace或static。

**【正确示例】**

```
// Foo.cpp
namespace {
void InternalFun()
{
    ...
}
}

const int MAX_COUNT = 20; // 仅供cpp文件内使用的const变量，可以不使用匿名namespace或者static修饰

void Foo::Fun()
{
    int i = MAX_COUNT;
    ...
    InternalFun();
}

```
**【错误示例】**

```
##### 场景1：cpp文件中不需要导出的函数有对外属性
- 错误示例：

```cpp
// cpp文件
void Foo() // 不符合：有对外属性
{
    ...
}
```

```
**【修复建议】**

用匿名namespace进行封装或者用static修饰
