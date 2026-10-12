# G.OBJ.05 避免基本类型与其包装类型的同名重载方法

- **规则ID**：33abc1ea-4022-4fe9-a2f4-cfd99a027c13
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

方法的重载特性允许声明名字相同、参数不同的方法（含构造方法），编译器在每次调用时都会去探查与调用参数相匹配的方法。但在自动装箱和泛型场景下，可能会导致各个重载方法之间的边界变得模糊，增加代码维护的难度，弄不清楚实际调用的是哪个方法。

**【正确示例】**

```
##### 场景1：
- 修复示例：

```java
class SomeResource {
    HashMap<Integer, Integer> hm = ...;
    public static Employee createSomeResourceByInt(int id, String name) {
        // 非重载，使用int类型的id构造对象
    }
    public static Employee createSomeResourceByInteger(Integer id, String name) {
        // 非重载，使用Integer类型的id构造对象
    }
    public Integer getDataByIndex(int id) {
        // 非重载
    }
    public String getDataByValue(Integer id) {
        // 非重载
    }
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

```java
class SomeResource {
    HashMap<Integer, Integer> hm = ...;
    public SomeResource(int id, String name) {
        ...
    }
    public SomeResource(Integer id, String name) {
        ...
    }
    public String getData(Integer id) {
        // 获取一个特定的记录
        String str = hm.get(id).toString();
        return str + SUFFIX;
    }
    public Integer getData(int id) {
        // 获取在位置id的记录
        return hm.get(id);
    }
}
```


```
**【修复建议】**

对于重载方法，方法的参数类型要清晰明确，避免出现参数类型差别为封装类型与基本类型的重载方法。当方法的参数类型确实仅存在封装类型与基本类型的差别时，建议通过方法名进行区分。
