# G.STD.08-CPP 外部数据用于容器索引或迭代器时必须确保在有效范围内

- **规则ID**：ce7a50b2-ff7a-4754-acab-54643a186cef
- **更新时间**：2025-03-25 19:23:27

---

**【问题级别】**

一般

**【描述】**

外部数据是不可信数据，当将外部数据用于容器或数组的索引时，应确保其值在容器或数组可被访问元素的有效范围内；当将外部数据用于迭代器偏移时，应确保偏移后的迭代器值在相应容器迭代器的有效范围内。



对于具有at()方法的容器（如std::vector, std::set, std::map），对应索引越界或键值内容不存在时，方法将抛出异常；而其对应的operator[]出现索引越界时，将导致未定义行为；或者因键值内容不存在而构造对应键值的默认值不成功时，也将导致未定义行为。

**【正确示例】**

```
std::vector<char> c{'A', 'B', 'C', 'D'};
int index = GetInputIndex();

try {
    std::cout << c.at(index) << std::endl; // 符合：索引越界时，at函数将抛出异常
} catch (const std::out_of_range& e) {
    ... // 错误处理
}
std::vector<char> c{'A', 'B', 'C', 'D'};
int index = GetInputIndex();

// 检查index的范围，确保index在容器元素的位置范围
if (index < 0 || index >= c.size()) {
    ... // 错误处理
}

std::cout << c[index] << std::endl;        // 符合：已检查过index的范围

// 符合：已检查过index的范围
for (auto pos = std::cbegin(c) + index; pos < std::cend(c); ++pos) {
    std::cout << *pos << std::endl;
}
void Foo(size_t n)
{
    std::vector<int> v{1, 2, 3};

    // 必须确保for_each_n的迭代范围[first, first + count)有效
    if (n > v.size()) {
        ... // 错误处理
    }
    for_each_n(v.cbegin(), n, [](int x) { std::cout << x; });
}

```
**【错误示例】**

```
std::vector<char> c{'A', 'B', 'C', 'D'};
int index = GetInputIndex();

// 不符合：没有正确校验index的范围，溢出读取：需要确保index在容器元素的位置范围
std::cout << c[index] << std::endl;

// 不符合：需要确保index在容器/数组元素的位置范围
for (auto pos = std::cbegin(c) + index; pos < std::cend(c); ++pos) {
    std::cout << *pos << std::endl;
}
void Foo(size_t n)
{
    std::vector<int> v{1, 2, 3};

    // n为外部的API传入的索引，可能导致越界访问
    for_each_n(v.cbegin(), n, [](int x) { std::cout << x; });
}

```
**【修复建议】**

输入校验包括但不局限于： 校验数据长度校验数据范围校验数据类型和格式校验输入只包含可接受的字符（“白名单”形式），尤其需要注意一些特殊情况下的特殊字符。
