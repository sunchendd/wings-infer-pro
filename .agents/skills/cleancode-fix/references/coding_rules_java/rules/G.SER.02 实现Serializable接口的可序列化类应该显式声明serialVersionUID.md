# G.SER.02 实现Serializable接口的可序列化类应该显式声明serialVersionUID

- **规则ID**：c9311235-56bd-424c-b8cd-3f1ba5ed303d
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

如果可序列化类未显式声明serialVersionUID，则序列化运行时将基于该类的各个方面计算该类的默认serialVersionUID值，如“Java(TM) 对象序列化规范”中所述。但是，强烈建议所有可序列化类都显式声明serialVersionUID值，原因是计算默认的serialVersionUID对类的详细信息具有较高的敏感性，根据编译器实现的不同可能千差万别，这样在反序列化过程中可能会导致意外的`InvalidClassException`。因此，为保证serialVersionUID值跨不同java编译器实现的一致性，序列化类必须声明一个明确的serialVersionUID值。



同时强烈建议使用private显式声明serialVersionUID，原因是这种声明仅应用于当前声明类，serialVersionUID作为继承成员没有用处。

**【正确示例】**

```
##### 场景1：
- 修复示例：显式声明serialVersionUID

  ```java
  public class BeanType implements Serializable {
      private static final long serialVersionUID = -2589766491699675794L;
      ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：实现Serializable接口的类未显式声明serialVersionUID

  ```java
  public class BeanType implements Serializable {
      ...
  }
  ```


```
**【修复建议】**

对于需要实现序列化接口的Class，应该显式声明serialVersionUID。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
