# G.RES.10-CPP 使用`std::make_shared`而不是`new`创建`std::shared_ptr`

- **规则ID**：c4476f2a-53fb-4a50-b224-ba8f665b23e4
- **更新时间**：2025-03-25 19:22:35

---

**【问题级别】**

严重

**【描述】**

使用std::make_shared除了类似std::make_unique一致性等原因外，还有性能的因素。



std::shared_ptr管理两个实体：



控制块(存储引用计数，deleter等)

管理对象

std::make_shared创建std::shared_ptr，会一次性在堆上分配足够容纳控制块和管理对象的内存。 而使用std::shared_ptr<SomeClass>(new SomeClass)创建std::shared_ptr，除了new SomeClass会触发一次堆分配外，std::shard_ptr的构造函数还会触发第二次堆分配，产生额外的开销。

**【正确示例】**

```


```
**【错误示例】**

```


```
**【修复建议】**

使用std::make_shared来创建shared_ptr
