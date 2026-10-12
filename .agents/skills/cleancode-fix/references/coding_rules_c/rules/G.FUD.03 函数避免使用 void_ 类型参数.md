# G.FUD.03 函数避免使用 void* 类型参数

- **规则ID**：913a65c4-94e9-4d2d-a66f-b39331d29844
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

一般

**【描述】**

函数参数应尽量避免使用`void*`类型，让编译器在编译时就检查出类型不匹配的问题。

**【正确示例】**

```
##### 场景1：使用void*传参
- 修复示例：

  ```c
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
##### 场景1：使用void*传参
- 错误示例：

  ```c
  void Fun(void *node) // 不符合： 这里用 void* 类型传递参数
  {
      if (node == NULL) {
          return;
      }
      Foo* foo = (Foo*)node;
      foo->DoSomeThing();
  }
  ```

```
**【修复建议】**

使用明确的参数类型，不要使用模糊的参数类型`void*`。
