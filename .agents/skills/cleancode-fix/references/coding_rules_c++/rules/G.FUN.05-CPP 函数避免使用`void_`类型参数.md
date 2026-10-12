# G.FUN.05-CPP 函数避免使用`void*`类型参数

- **规则ID**：aa4ba67b-3bf2-4cca-9cf6-5874a9594a21
- **更新时间**：2025-03-25 19:22:02

---

**【问题级别】**

一般

**【描述】**

函数参数应尽量避免使用 void* 类型，让编译器在编译时就检查出类型不匹配的问题：



在基于接口编程时，使用基类的引用或指针来作为函数参数

在使用泛型编程时，使用模板参数T&或T*来实现函数参数类型的变化

**【正确示例】**

```
##### 场景1：使用void*传参
- 修复示例：

  ```cpp
  void Fun(Foo *node) // 符合： 这里用明确的参数类型 Foo*
  {
      if (node == NULL) {
          return;
      }
      foo->DoSomeThing();
  }
  ```

```
**【错误示例】**

```
void Fun(void* node)       // 不符合： 这里用 void* 类型传递参数
{
    if (node == nullptr) {
        return;
    }

    Foo* foo = static_cast<Foo*>(node);
    foo->DoSomeThing();
}

void Call()
{
    Foo* foo = nullptr;
    Bar* bar = nullptr;
    ...
    Fun(bar);              // 不符合：这里本意是想传递参数 foo，但错传了bar，却没有编译错误
}

```
**【修复建议】**

避免使用void *参数类型
