# G.ENU.01-CPP 优先使用枚举类而不是普通枚举

- **规则ID**：9e07d7e4-7786-45a0-b5e0-3ef59ea4c579
- **更新时间**：2025-03-25 19:22:15

---

**【问题级别】**

一般

**【描述】**

基于C++的作用域常识，在大括号中声明的变量名在括号之外是不可见的。但是这对普通枚举(unscoped enum)中的枚举项并不成立。普通枚举的枚举项和它的枚举类型同属于一个作用域空间，这会导致命名空间污染，因而在这个作用域内不能再使用相同标识符声明变量，这可能也会让程序员对变量作用域产生困惑。

**【正确示例】**

```
enum class State { DEFAULT, RUNNING, STOP };

constexpr int DEFAULT = 1;

```
**【错误示例】**

```
enum State { DEFAULT, RUNNING, STOP };

constexpr int DEFAULT = 1; // 编译错误：'DEFAULT' already declared in this scope

```
**【修复建议】**

修改为scoped枚举类型
