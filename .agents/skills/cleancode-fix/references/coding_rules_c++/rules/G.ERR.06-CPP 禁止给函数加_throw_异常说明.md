# G.ERR.06-CPP 禁止给函数加"throw"异常说明

- **规则ID**：b5ab6aa0-01c6-49d5-8229-ecb3b047eb09
- **更新时间**：2025-03-25 19:22:42

---

**【问题级别】**

严重

**【描述】**

给函数加throw(...)异常说明的语法，从C++11开始被弃用，在C++17中被去除（throw()在C++20中被去除）。现代的C++中，除非函数不抛任何异常（通过noexcept标记），否则无需专门标记。



在C++11之前，用throw(X, Y)这种方式标记，意思是函数只能抛出X, Y这几个异常。在运行时，如果该函数抛出除X, Y之外的其他异常，会导致std::unexpected被调用，默认导致std::terminate。但如果该函数调用了其他模块中定义的函数，那么被调函数行为的变化很有可能导致新的异常（如Z）被抛出，这就要导致异常说明中添加新的异常，即throw(X, Y, Z)，而当前函数的调用者也要跟着一起改变，这样不仅没有处理新的异常（注意：系统中能处理该异常的层次往往离该异常抛出的层次很远），还增加了维护的开销。



比较新的GCC和Clang编译器加上-Wall和-Wdeprecated选项可以对这一问题给出警告。

**【正确示例】**

```
void Foo()
{
    Bar(); // 不管Bar抛出什么异常，都可以继续抛出Foo
}

```
**【错误示例】**

```
// warning: dynamic exception specifications are deprecated
void Foo() throw (AException, BException)
{
    // 万一Bar函数的行为变化了，抛出了除了AException和BException以外的其他异常，
    // 就会导致std::terminate而不是异常继续向上抛
    Bar();
}

```
**【修复建议】**

用noexcept标记
