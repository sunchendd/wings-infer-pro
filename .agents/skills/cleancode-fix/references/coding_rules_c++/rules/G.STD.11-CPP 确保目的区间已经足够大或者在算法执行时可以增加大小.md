# G.STD.11-CPP 确保目的区间已经足够大或者在算法执行时可以增加大小

- **规则ID**：f808cdee-f462-4aeb-b616-c4fcf359d20c
- **更新时间**：2025-03-25 19:23:29

---

**【问题级别】**

一般

**【描述】**

给容器添加新的元素时，必须确保不超出容器的大小或者自动扩充容器以容纳新增的元素。



当使用标准库中的算法函数需要在容器尾部自动插入元素并且容器支持push_back时，可以在算法中使用封装了容器对象的std::back_insert_iterator<C> 迭代器（其中C是容器类型，一般使用std::back_inserter(c) 便捷函数产生该迭代器）。



同样，当使用算法函数需要在容器头部自动插入元素并且容器支持push_front时，可以使用std::front_inserter(c) 便捷函数产生的std::front_insert_iterator<C> 迭代器。

**【正确示例】**

```
std::vector<int> src{1, 2, 3};
std::vector<long> dest;

// 符合：调整dest的大小
dest.resize(src.size());
std::transform(src.cbegin(), src.cend(), dest.begin(),
               [](int x) -> long { return x; });
std::vector<int> src{1, 2, 3};
std::vector<long> dest;

// 符合：使用std::back_inserter自动扩充容器大小
std::transform(src.cbegin(), src.cend(), std::back_inserter(dest),
               [](int x) -> long { return x; });
std::vector<size_t> v{1, 2, 3};

// 符合：更新自身元素值，能够保证有足够的空间来容纳更新的值
std::transform(v.cbegin(), v.cend(), v.begin(), [](size_t n) { return n % 2; });

```
**【错误示例】**

```
std::vector<int> src{1, 2, 3};
std::vector<long> dest;

// 不符合：dest不足以容纳新增加的元素
std::transform(src.cbegin(), src.cend(), dest.begin(),
               [](int x) -> long { return x; });

```
**【修复建议】**

使用标准库算法函数（包括std::copy, std::copy_n, std::fill_n, std::transform）操作标准库容器时，要确保目标容器的容量足够大，或者使用insert_iterator迭代目标容器，使其在算法执行时增加容器的的大小。
