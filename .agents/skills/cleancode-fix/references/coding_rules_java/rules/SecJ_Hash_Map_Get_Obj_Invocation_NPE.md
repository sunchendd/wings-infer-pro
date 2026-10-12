# SecJ_Hash_Map_Get_Obj_Invocation_NPE

- **规则ID**：fbfe5689-4af3-449b-84e5-eaaec93249c4
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

在Java代码实现时，通过Hashmap的get方法获取对象，并且不是使用Hashmap的Iterator获取，如果key不存在时获取的对象为null，在使用此对象可能出现java.lang.NullPointerException的异常，app出现Crash。

**【正确示例】**

```
- 使用默认值

```java

private HashMap<String, String> datas = new HashMap<>();



public void dealName() {

// 【GOOD】可以使用getOrDefault指定value为null后的默认值

String name = datas.getOrDefault("id01", "");

String lowName = name.toLowerCase(Locale.ENGLISH);

}

```

- 使用Optional类对获取到的对象进行包装，然后使用ifPresent方法来执行操作

```java

Optional<Object> optional = Optional.ofNullable(hashMap.get(key));

// 【GOOD】使用Optional类进行包装

optional.ifPresent(obj -> {

// 使用 obj 进行操作

});

```

- 在使用获取到的对象之前，先进行空值检查

```java

Object obj = hashMap.get(key);

// 【GOOD】使用获取到的obj之前，先进行空值检查

if (obj != null) {

// 使用 obj 进行操作

}

```

```
**【错误示例】**

```
```java

private HashMap<String, String> datas = new HashMap<>();



public void dealName() {

String name = datas.get("id01");

/*

* 【不符合】:

* 在Java代码实现时，通过Hashmap的get方法获取对象，并且不是使用Hashmap的Iterator获取，如果key不存在时获取的对象为null，在使用此对象可能出现java.lang.

* NullPointerException的异常，app出现Crash。

*/

String lowName = name.toLowerCase(Locale.ENGLISH);

}

```

```
**【修复建议】**

HashMap获取值后，对value为null的场景进行提前判空处理。
