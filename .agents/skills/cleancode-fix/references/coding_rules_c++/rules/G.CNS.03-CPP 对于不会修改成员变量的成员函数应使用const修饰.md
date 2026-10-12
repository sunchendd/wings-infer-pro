# G.CNS.03-CPP 对于不会修改成员变量的成员函数应使用const修饰

- **规则ID**：031178ea-1b09-48bb-86cd-ee1f082a4eed
- **更新时间**：2025-03-25 19:22:14

---

**【问题级别】**

一般

**【描述】**

只要不修改成员变量的成员函数，都应使用const修饰。访问函数应该总是 const。对于虚函数，应当从设计意图上考虑继承链上的所有类是否需要在此虚函数中修改成员变量，而不是仅关注单个类的实现。

**【正确示例】**

```
##### 场景1：函数本意是不需要修改成员变量，但未加const保护
- 修复示例1：在函数声明中添加const

```c++
class Foo {
public:
    ...
    void PrintValue() const  // 符合
    {
        std::cout << value;
    }
    int GetValue() const    // 符合
    {
        return value;
    }
private:
    int value;
};
```

```
**【错误示例】**

```
##### 场景1：函数本意是不需要修改成员变量，但未加const保护
- 错误示例：

```c++
class Foo {
public:
    ...
    void PrintValue()  // 不符合
    {
        std::cout << value;
    }
    int GetValue()    // 不符合
    {
        return value;
    }
private:
    int value;
};
```

```
**【修复建议】**

添加const修饰符
