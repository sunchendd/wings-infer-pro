# SecJ_Forbid_Serialize_Nonstatic_Inner_Class

- **规则ID**：bcef5521-5eee-4574-94c3-f59cb84c0fe3
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

对内部类进行序列化会导致对外部类也执行序列化，因此，如果外部类是不可序列化的，则可能会造成信息泄露或出现运行时错误。此外，由于 Java 编译器创建了合成字段以便实施内部类，因此对内部类执行序列化会导致出现平台依赖，但是依据不同的实施方法和不同的编译器，出现的情况也会有所不同。

**【正确示例】**

```
```java

class CWE398_Bad_01 {

private int accessLevel;

// 【GOOD】 ： 反序列化静态的内部类

static class Registrator implements Serializable {

private String data;



public Registrator(String data) {

this.data = data;

}



public void show() {

System.out.println(data);

}

...

}

}

```

```
**【错误示例】**

```
```java

class CWE398_Bad_01 {

private int accessLevel;



// 【不符合】: 序列化非静态的内部类，导致外部类也被序列化，但是外部类没有实现Serializable接口

class Registrator implements Serializable {

private String data;



public Registrator(String data){

this.data = data;

}



public void show(){

System.out.println(data);

}

...

}

}

```

```
**【修复建议】**

在使用内部类时，不应对其进行序列化，否则它们将变为静态嵌套类，由此就不会出现对非静态内部类执行序列化时会出现的问题。如果嵌套类为静态类型，则其本质上与实例变量并无关联（包括外部类的实例变量），并且不会导致对外部类执行序列化。
