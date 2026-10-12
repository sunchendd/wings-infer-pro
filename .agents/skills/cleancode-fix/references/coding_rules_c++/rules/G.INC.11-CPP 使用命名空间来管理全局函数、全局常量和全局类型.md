# G.INC.11-CPP 使用命名空间来管理全局函数、全局常量和全局类型

- **规则ID**：938d533a-12a5-4b48-b2e3-56a7be003e93
- **更新时间**：2025-03-25 19:22:56

---

**【问题级别】**

一般

**【描述】**

将全局函数、全局常量、全局类型以及类型别名放在命名空间内可避免污染全局作用域。如果它们和某个类有紧密联系，那么可以作为类的静态成员函数、静态成员常量等；如果它们被用于C语言接口，那么可以放在全局作用域。

**【正确示例】**

```
namespace Utils {
const int MAX_SIZE = 100;

int Add(int a, int b);

class File {
public:
    static const std::string SEPARATOR;
    static File CreateTempFile(const std::string& fileName);
};
}

```
**【错误示例】**

```
##### 场景1：全局类型以及类型别名放在全局作用域
- 错误示例：

```cpp
using Alias = Type;     // 不符合：全局类型别名放在全局作用域
typedef Type Alias;     // 不符合：全局类型别名放在全局作用域

class File { ... };     // 不符合：全局类型放在全局作用域
struct Color { ... };   // 不符合：全局类型放在全局作用域
```
##### 场景2：全局函数放在全局作用域
- 错误示例：

```cpp
File CreateTempFile(const std::string& fileName);   // 不符合：全局函数放在全局作用域
```
##### 场景3：全局常量放在全局作用域
- 错误示例：

```cpp
constexpr int MAX_SIZE = 100;   // 不符合：全局常量放在全局作用域
```

```
**【修复建议】**

使用命名空间来管理全局函数、常量等
