# G.STD.09-CPP 使用有效的迭代器和指向容器元素的指针与引用

- **规则ID**：33a205fc-70b7-4790-bfd1-20a10c70c9b4
- **更新时间**：2025-03-25 19:23:28

---

**【问题级别】**

致命

**【描述】**

使用迭代器可以便捷地访问容器中的元素，迭代过程中应确保迭代器始终有效，否则会使程序产生未定义行为。同样，也应确保使用有效的指向容器元素的指针与引用来访问容器中的元素。如：std::string类的c_str()、data()返回的指针，std::vector、std::string类的front()返回的引用等。



常见场景如下：



使用迭代器访问容器中的元素前必须保证迭代器有效。如：std::find()、std::find_if()等算法可能返回无效位置，在使用返回的迭代器时需要校验其有效性

容器被更新后，应该同时更新已有的迭代器。如：调用erase()、insert()等方法后，已有的迭代器可能会失效

容器中的元素被销毁后，不应再使用已有的迭代器访问容器中的元素。如：调用clear()方法后

**【正确示例】**

```
std::vector<int> data;
...
auto pos = std::find(data.begin(), data.end(), SOME_VALUE);
if (pos != data.end()) {
    std::cout << *pos;                                      // 符合：确保迭代器有效
}

使用erase函数的返回值作为新的迭代器。

std::vector<int> data;
...
auto pos = data.begin();
while (pos != data.end()) {
    if (*pos == SOME_VALUE) {
        pos = data.erase(pos);                             // 符合：更新已有迭代器
    } else {
        ++pos;
    }
}

```
**【错误示例】**

```
如下代码中，未检查迭代器是否有效。

std::vector<int> data;
...
auto pos = std::find(data.begin(), data.end(), SOME_VALUE);
std::cout << *pos;                                          // 不符合：迭代器可能无效

如下代码中，调用erase函数后未更新迭代器。

std::vector<int> data;
...
auto pos = data.begin();
while (pos != data.end()) {
    if (*pos == SOME_VALUE) {
        data.erase(pos);                                    // 不符合：pos已失效
    }
    ++pos;
}

```
**【修复建议】**

使用迭代子之前请确保迭代子指向的内容有效。不要使用end函数返回的迭代子。不要使用无效的迭代子。
