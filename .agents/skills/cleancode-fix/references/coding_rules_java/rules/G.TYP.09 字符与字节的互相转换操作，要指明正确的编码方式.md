# G.TYP.09 字符与字节的互相转换操作，要指明正确的编码方式

- **规则ID**：7fb24292-32a1-4558-b3b9-d4cc64121c93
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

Java虚拟机采用编码方式默认与操作系统的字符编码方式相同，String的编码方式、`String.getBytes()`默认采用Java虚拟机编码。当跨平台实现字符与字节之间的转换，可能会导致乱码，所以字符与字节之间转换时要明确指定编码方式，推荐优先采用UTF-8编码。

**【正确示例】**

```
##### 场景1：字符与字节的互相转换操作未指明编码方式

- 修复示例：

  ```java
  String data = "123ABC中国";
  byte[] buf = data.getBytes(StandardCharsets.UTF_8);
  // 跨平台传输buf
  ...
  String result = new String(buf, StandardCharsets.UTF_8);
  ```

##### 场景2：读取文件时，指定对应的编码方式

- 修复示例：

  ```java
  String line;
  try (FileInputStream fis = new FileInputStream(fileName);
      InputStreamReader isr = new InputStreamReader(fis, StandardCharsets.UTF_8);
      BufferedReader br = new BufferedReader(isr)) {
      line = br.readLine();
      ...
  }
  ```

##### 场景3：url编/解码时，指定对应的编码方式

- 修复示例：

  ```java
    public String encodeUrl(String url){
        return URLEncoder.encode("xxx", StandardCharsets.UTF_8);
    }

    public String decodeUrl(String url){
        return URLDecoder.decode(url, StandardCharsets.UTF_8);
    }
  ```

```
**【错误示例】**

```
##### 场景1：字符与字节的互相转换操作未指明编码方式

- 错误示例：

  ```java
  String data = "123ABC中国";
  byte[] buf = data.getBytes();
  // 跨平台传输buf
  ...
  String result = new String(buf);
  ```

##### 场景2：读取文件时，指定对应的编码方式

- 错误示例：

  ```java
  String line;
  try (FileReader fr = new FileReader(fileName);
      BufferedReader br = new BufferedReader(fr)) {
      line = br.readLine();
      ...
  }
  ```

##### 场景3：url编/解码时，指定对应的编码方式

- 错误示例：

  ```java
    public String encodeUrl(String url){
        return URLEncoder.encode(url);
    }

    public String decodeUrl(String url){
        return URLDecoder.decode(url);
    }
  ```

```
**【修复建议】**

字符与字节的互相转换操作，要指明编码方式，推荐优先采用UTF_8编码。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
