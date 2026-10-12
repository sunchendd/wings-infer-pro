# G.FUD.01 对象或函数的所有声明必须与定义具有一致的名称和类型限定符

- **规则ID**：d8ed5453-c743-4d7d-86a3-d063f7baa9dc
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

函数或对象的声明和定义之间的不一致可能导致编程错误，或者使用错误。

**【正确示例】**

```
##### 场景1：缺少参数名
- 修复示例：

  ```c
  // Fun.h
  void Fun1(int num); // 符合：增加参数名，和定义保持一致

  // Fun.c
  void Fun1(int num)
  {
      ...
  }
  ```
##### 场景2：参数名不匹配
- 修复示例：

  ```c
  // Fun.h
  void Fun2(int num, int count); // 符合：修改参数名，和定义保持一致

  // Fun.c
  void Fun2(int num, int count)
  {
      ...
  }
  ```
##### 场景3：无参数时缺少void
- 修复示例：

  ```c
  // Fun.h
  void Fun(void); // 符合
  void (*Fp1)(void); // 符合
  // Fun.c
  void Fun(void)
  {
      ...
  }
  ```
##### 场景4：参数的限定符与函数定义不一致
- 修复示例：

  ```c
  // Fun.h
  void Func(const int num); // 符合

  // Fun.c
  void Func(const int num) // 符合
  {
      ...
  }
  ```

```
**【错误示例】**

```
##### 场景1：缺少参数名
- 错误示例：

  ```c
  // Fun.h
  void Fun1(int); // 不符合：缺少参数名，应修改为void Fun1(int num)
  
  // Fun.c
  void Fun1(int num)
  {
      ...
  }
  ```
##### 场景2：参数名不匹配
- 错误示例：

  ```c
  // Fun.h
  void Fun2(int count, int num); // 不符合：参数名不匹配，应修改为 void Fun2(int num, int count)

  // Fun.c
  void Fun2(int num, int count)
  {
      ...
  }
  ```
##### 场景3：无参数时缺少void
- 错误示例：

  ```c
  // Fun.h
  void Fun(); // 不符合，没有参数时需要加void
  void (*Fp1)(); // 不符合：空参数列表，应修改为void (*Fp1)(void)

  // Fun.c
  void Fun()
  {
      ...
  }
  ```
##### 场景4：参数的限定符与函数定义不一致
- 错误示例：

  ```c
  // Fun.h
  void Func(const int num); // 不符合：参数的限定符与函数定义不一致

  // Fun.c
  void Func(int num) // 不符合： 参数的限定符与函数声明不一致
  {
      ...
  }
  ```

```
**【修复建议】**

- 函数声明中的参数应该包含参数名，并且函数定义与其声明中的参数类型以及参数名需要保持一致。

- 如果一个函数定义中没有参数，则在其所有声明与定义中使用关键字void。

- 同一个对象或函数的所有声明和定义应保持一致，包括类型、限定符等。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
