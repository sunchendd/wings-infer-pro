# G.EXP.19-CPP 禁止使用std::move操作const对象

- **规则ID**：95e09a53-f1ef-42b6-be6b-22890af521fe
- **更新时间**：2025-03-25 19:22:24

---

**【问题级别】**

严重

**【描述】**

从字面上看，std::move的意思是要移动一个对象。而const对象是不允许修改的，自然也无法移动。因此用std::move操作const对象会给代码阅读者带来困惑。

在实际功能上，std::move会把对象转换成右值引用类型；对于const对象，会将其转换成const的右值引用。由于极少有类型会定义以const右值引用为参数的移动构造函数和移动赋值操作符，因此代码实际功能往往退化成了对象拷贝而不是对象移动，带来了性能上的损失。

**【正确示例】**

```
##### 场景1：使用`std::move`操作`const`对象。
- 修复示例：

```cpp
void Func1()
{
    const std::string str{"String content"};
    std::string name = str;             // 符合：进行复制
}

void Func2()
{
    std::string str{"String content"};
    std::string name = std::move(str);  // 符合：移动非const对象
}

void Func3()
{
    const std::string str{"String content"};
    std::vector<std::string> names;
    names.push_back(str);               // 符合：进行复制
}
```

```
**【错误示例】**

```
const std::string str{"String content"};
std::string name = std::move(str);       // 不符合：并没有移动str，而是进行了复制
const std::string str{"String content"};
std::vector<std::string> names;
names.push_back(std::move(str));         // 不符合：并没有移动str，而是进行了复制

```
**【修复建议】**

禁止std_move操作const对象
