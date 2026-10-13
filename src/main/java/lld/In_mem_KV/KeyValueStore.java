public class KeyValueStore{

    private static class Entry{
        String Key;
        String Value;
        Entry Next;

        Entry(String Key, String Value) {
            this.Key = Key;
            this.Value = Value;
        }
    }

    private Entry[] buckets;
    private int size;

    public KeyValueStore(int capacity){
        buckets = new Entry[capacity];
    }

    //hash function for bucket assignment

    private int hash(String key) {
        //implement 31*charvalue and append to final value
        //bit wise xor with 2^16
        //(h & 0x7fffffff) % buckets.length;
    }

    //handle collisions here in put()

    public void put(String key, String value){
        int index = hash(key);

        Entry current = buckets[index];

        while(current != null){
            if(current.Key.equals(key)) {
                current.value = value;
                return;
            }

            current = current.next;
        }

        Entry entry = new Entry(key,value);

        entry.next = buckets[index];
        buckets[index] = entry;

        size++;
    }


    //writing get

    public String get(String key){
        int index = hash(key);

        Entry current = buckets[index];

        while(current!=null){
            if(current.Key.equals(key)){
                return current.Value;
            }
            current = current.next;
        }

        return null;
    }


    // delete handling

    public boolean delete(String key){
        int index = hash(key);

        Entry current = buckets[index];

        Entry previous = null;

        while(current!=null){

            if(current.Key.equals(key)){

                if(previous == null){
                    buckets[index] = current.next;
                }
                else{
                    previous.next = current.next;
                }

                size--;

                return true;
            }

            previous = current;
            current = current.next;
        }

        return false;
    }


}