# G.STD.10-CPP 在不需要修改迭代器指向的对象时，应使用const_iterator

- **规则ID**：ac6a5ec7-50d5-4c3c-ab23-9d605126e98d
- **更新时间**：2025-03-25 19:22:59

---

**【问题级别】**

一般

**【描述】**

使用迭代器可以便捷的访问容器中的元素，它分为普通的迭代器iterator，和const的迭代器const_iterator两种：



iterator可以修改元素值，在解引用迭代器时可得到一个对象的非const引用

const_iterator不可以修改元素值，在解引用迭代器时得到一个对象的const引用

在不需要修改迭代器指向的对象时（如只读取对象的值，且仅使用对象的const方法），应使用容器的const_iterator。



从C++11开始，std::vector、std::list等容器新增了cbegin()和cend()方法，专门返回const_iterator。使用它们获取容器的const_iterator，可以使代码语意更加清晰明确。

**【正确示例】**

```
// 符合：使用了const_iterator
for (auto iter = c.cbegin(); iter != c.cend(); ++iter) {
    std::cout << *iter << std::endl;
}

void Bar(const std::string& content)
{
    ...
}

void Foo()
{
    std::vector<std::string> contents;
    ...
    for (auto iter = contents.cbegin(); iter != contents.cend(); ++iter) { // 符合
        Bar(*iter);
    }
}

```
**【错误示例】**

```
// 不符合：代码没有对元素的内容进行修改，应使用cbegin()和cend()
for (auto iter = c.begin(); iter != c.end(); ++iter) {
    std::cout << *iter << std::endl;
}

```
**【修复建议】**

使用const迭代器
