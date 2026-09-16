// Requires libxml2
#include <arpa/inet.h>
#include <libxml/parser.h>
#include <libxml/tree.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define BUFFER_SIZE 4096

typedef struct {
  char *format;
  char *date;
  char *time;
  int frame;
  int fs;
  int n;
  int bits;
  int channels;
  char **channel_names;
  char **channel_types;
  char **channel_phases;
  int *channel_ranges;
  char **channel_payloads;
} OpenPMUData;

void parse_openpmu(xmlDocPtr doc, OpenPMUData *data) {
  xmlNodePtr root = xmlDocGetRootElement(doc);
  if (!root)
    return;

  xmlNodePtr node = root->children;
  while (node) {
    if (node->type == XML_ELEMENT_NODE) {
      if (strcmp((char *)node->name, "Format") == 0) {
        data->format = strdup((char *)xmlNodeGetContent(node));
      } else if (strcmp((char *)node->name, "Date") == 0) {
        data->date = strdup((char *)xmlNodeGetContent(node));
      } else if (strcmp((char *)node->name, "Time") == 0) {
        data->time = strdup((char *)xmlNodeGetContent(node));
      } else if (strcmp((char *)node->name, "Frame") == 0) {
        data->frame = atoi((char *)xmlNodeGetContent(node));
      } else if (strcmp((char *)node->name, "Fs") == 0) {
        data->fs = atoi((char *)xmlNodeGetContent(node));
      } else if (strcmp((char *)node->name, "n") == 0) {
        data->n = atoi((char *)xmlNodeGetContent(node));
      } else if (strcmp((char *)node->name, "bits") == 0) {
        data->bits = atoi((char *)xmlNodeGetContent(node));
      } else if (strcmp((char *)node->name, "Channels") == 0) {
        data->channels = atoi((char *)xmlNodeGetContent(node));
        data->channel_names = malloc(data->channels * sizeof(char *));
        data->channel_types = malloc(data->channels * sizeof(char *));
        data->channel_phases = malloc(data->channels * sizeof(char *));
        data->channel_ranges = malloc(data->channels * sizeof(int));
        data->channel_payloads = malloc(data->channels * sizeof(char *));
      } else if (strncmp((char *)node->name, "Channel_", 8) == 0) {
        int index = atoi((char *)node->name + 8);
        if (index >= 0 && index < data->channels) {
          xmlNodePtr child = node->children;
          while (child) {
            if (child->type == XML_ELEMENT_NODE) {
              char *content = (char *)xmlNodeGetContent(child);
              if (strcmp((char *)child->name, "Name") == 0) {
                data->channel_names[index] = strdup(content);
              } else if (strcmp((char *)child->name, "Type") == 0) {
                data->channel_types[index] = strdup(content);
              } else if (strcmp((char *)child->name, "Phase") == 0) {
                data->channel_phases[index] = strdup(content);
              } else if (strcmp((char *)child->name, "Range") == 0) {
                data->channel_ranges[index] = atoi(content);
              } else if (strcmp((char *)child->name, "Payload") == 0) {
                data->channel_payloads[index] = strdup(content);
              }
              xmlFree(content);
            }
            child = child->next;
          }
        }
      }
    }
    node = node->next;
  }
}

void free_openpmu_data(OpenPMUData *data) {
  if (data->format)
    free(data->format);
  if (data->date)
    free(data->date);
  if (data->time)
    free(data->time);
  for (int i = 0; i < data->channels; i++) {
    if (data->channel_names[i])
      free(data->channel_names[i]);
    if (data->channel_types[i])
      free(data->channel_types[i]);
    if (data->channel_phases[i])
      free(data->channel_phases[i]);
    if (data->channel_payloads[i])
      free(data->channel_payloads[i]);
  }
  if (data->channel_names)
    free(data->channel_names);
  if (data->channel_types)
    free(data->channel_types);
  if (data->channel_phases)
    free(data->channel_phases);
  if (data->channel_ranges)
    free(data->channel_ranges);
  if (data->channel_payloads)
    free(data->channel_payloads);
}

int parse_udp_stream(int port, OpenPMUData *data) {
  int sockfd;
  struct sockaddr_in server_addr, client_addr;
  socklen_t client_len = sizeof(client_addr);
  char buffer[BUFFER_SIZE];

  sockfd = socket(AF_INET, SOCK_DGRAM, 0);
  if (sockfd < 0) {
    perror("socket creation failed");
    return 0;
  }

  memset(&server_addr, 0, sizeof(server_addr));
  server_addr.sin_family = AF_INET;
  server_addr.sin_addr.s_addr = INADDR_ANY;
  server_addr.sin_port = htons(port);

  if (bind(sockfd, (const struct sockaddr *)&server_addr, sizeof(server_addr)) <
      0) {
    perror("bind failed");
    close(sockfd);
    return 0;
  }

  printf("Listening for UDP data on port %d...\n", port);
  ssize_t len = recvfrom(sockfd, buffer, BUFFER_SIZE, 0,
                         (struct sockaddr *)&client_addr, &client_len);
  if (len < 0) {
    perror("recvfrom failed");
    close(sockfd);
    return 0;
  }
  buffer[len] = '\0';

  xmlDocPtr doc = xmlReadMemory(buffer, len, "noname.xml", NULL, 0);
  if (!doc) {
    fprintf(stderr, "Failed to parse XML\n");
    close(sockfd);
    return 0;
  }

  parse_openpmu(doc, data);
  xmlFreeDoc(doc);
  close(sockfd);
  return 1;
}

int main(int argc, char *argv[]) {
  OpenPMUData data = {0};

  // Parse from file
  if (argc > 1) {
    xmlDocPtr doc = xmlReadFile(argv[1], NULL, 0);
    if (doc) {
      parse_openpmu(doc, &data);
      printf("Data from file %s:\n", argv[1]);
      printf("Format: %s\n", data.format);
      printf("Date: %s\n", data.date);
      printf("Time: %s\n", data.time);
      printf("Frame: %d\n", data.frame);
      printf("Fs: %d\n", data.fs);
      printf("n: %d\n", data.n);
      printf("bits: %d\n", data.bits);
      printf("Channels: %d\n", data.channels);
      for (int i = 0; i < data.channels; i++) {
        printf("Channel %d:\n", i);
        printf("  Name: %s\n", data.channel_names[i]);
        printf("  Type: %s\n", data.channel_types[i]);
        printf("  Phase: %s\n", data.channel_phases[i]);
        printf("  Range: %d\n", data.channel_ranges[i]);
        printf("  Payload length: %zu\n", strlen(data.channel_payloads[i]));
      }
      xmlFreeDoc(doc);
    }
  }

  // Parse from UDP stream
  if (parse_udp_stream(5000, &data)) {
    printf("\nData from UDP stream:\n");
    printf("Format: %s\n", data.format);
    printf("Date: %s\n", data.date);
    printf("Time: %s\n", data.time);
    printf("Frame: %d\n", data.frame);
    printf("Fs: %d\n", data.fs);
    printf("n: %d\n", data.n);
    printf("bits: %d\n", data.bits);
    printf("Channels: %d\n", data.channels);
    for (int i = 0; i < data.channels; i++) {
      printf("Channel %d:\n", i);
      printf("  Name: %s\n", data.channel_names[i]);
      printf("  Type: %s\n", data.channel_types[i]);
      printf("  Phase: %s\n", data.channel_phases[i]);
      printf("  Range: %d\n", data.channel_ranges[i]);
      printf("  Payload length: %zu\n", strlen(data.channel_payloads[i]));
    }
  }

  free_openpmu_data(&data);
  return 0;
}
