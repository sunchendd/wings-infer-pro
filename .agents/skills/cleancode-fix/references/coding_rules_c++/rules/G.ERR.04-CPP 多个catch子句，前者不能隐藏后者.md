# G.ERR.04-CPP 多个catch子句，前者不能隐藏后者

- **规则ID**：2451a406-a54b-44d3-a562-2ca47686ed3f
- **更新时间**：2025-03-25 19:22:41

---

**【问题级别】**

严重

**【描述】**

当try-catch语句有多个catch子句时，如果前面的catch子句捕获的类型是后者的基类，那么后面的catch子句就永远不会被执行到。因此，catch的顺序应该是先捕获派生类（即更特殊的异常类型），后捕获基类（即更通用的异常类型）。



特别地，catch (...)可以捕获所有类型的异常。如果有，它应该是最后一个catch子句。

**【正确示例】**

```
try {
    DoSomething()
} catch (const BarException& e) {       // 符合：先捕获派生类
    ...
} catch (const FooException& e) {       // 符合：后捕获基类
    ...
} catch (const SomeOtherException& e) {
    ...
} catch (...) {                         // 符合：最后是catch(...)
    ...
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
class SomeOtherException : public std::exception {
    ...
};

try {
    DoSomething()
} catch (const FooException& e) {       // 不符合：使用基类会捕获所有的BarException
    ...
} catch (const BarException& e) {       // 这个子句永远不会被执行到
    ...
} catch (...) {                         // 不符合：这里会捕获所有的异常
    ...
} catch (const SomeOtherException& e) { // 这个子句也永远不会被执行到
    ...
}

```
**【修复建议】**

将被隐藏的catch语句往前提或者删掉
