# G.EXP.16-CPP 避免使用const_cast

- **规则ID**：367dcf64-4256-4d1f-a4f3-2ab0d72534d6
- **更新时间**：2025-03-25 19:22:24

---

**【问题级别】**

一般

**【描述】**

const_cast用于移除对象的const和volatile性质。使用const_cast转换后的指针或者引用来修改const对象或volatile对象，程序可能会产生未定义行为。

**【正确示例】**

```
##### 场景1：使用const_cast转换const指针
- 修复示例：

```cpp
int i = 1024; // 变量值会修改，删除const属性
int* p = &i;
*p = 2048; // 符合
```

```
**【错误示例】**

```
const int i = 1024; 
int* p = const_cast<int*>(&i);
*p = 2048;                              // 未定义行为
class Foo {
public:
    void SetValue(int v) { value = v; }

private:
    int value{0};
};

int main()
{
    const Foo foo;
    Foo* p = const_cast<Foo*>(&foo);
    p->SetValue(2);                     // 未定义行为
    return 0;
}

```
**【修复建议】**

避免使用const_cast
