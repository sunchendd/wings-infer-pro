# G.ERR.03-CPP 以左值引用的形式捕获异常

- **规则ID**：6bbcf376-0ea4-4d26-8825-47ba21868e42
- **更新时间**：2025-03-25 19:22:39

---

**【问题级别】**

严重

**【描述】**

异常可以用类的继承关系来组成层次结构。如果按值捕获异常的基类，而实际抛出的对象是派生类的实例，就会导致对象被切片。按引用捕获则不会有切片的问题。

**【正确示例】**

```
try {
    throw BarException();
} catch (const FooException& e) {            // 符合：按引用捕获，此时不会切片
    ...
}
try {
    throw BarException();
} catch (FooException& e) {                  // 符合：按非const引用捕获
    e.AddMoreInformation("some info");
    throw;
}

```
**【错误示例】**

```
class FooException : public std::exception {
    ...
};
class BarException : public FooException {
    ...
};

try {
    throw BarException();
} catch (FooException e) {                   // 不符合：被切片
    ...
}

```
**【修复建议】**

改成以左值引用形式捕获异常
